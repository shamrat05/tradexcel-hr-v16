"""Personal employee calendar: attendance, leave, holidays, off days, shifts, punches."""

from __future__ import annotations

import calendar as _calendar
from datetime import date, timedelta

import frappe
from frappe.utils import getdate


LEAVE_PALETTE = ("#b3cde3", "#ccebc5", "#fddaec", "#decbe4", "#fed9a6", "#ffffcc")
BASE_COLORS = {
    "Present": "#c6efce",
    "Half Day": "#ffe699",
    "Absent": "#ffc7ce",
    "Holiday": "#d9d2e9",
    "Weekly Off": "#e8eaed",
    "Punched Only": "#ffe0b2",
    "Future": "#fbfbfb",
    "No Record": "#ffffff",
}
LATE_COLOR = "#ffb74d"
EARLY_COLOR = "#ffd54f"


def leave_color(leave_type):
    """Deterministic color per leave type, so different types never share one blue."""
    if not leave_type:
        return "#bdd7ee"
    return LEAVE_PALETTE[sum(ord(char) for char in leave_type) % len(LEAVE_PALETTE)]


@frappe.whitelist()
def get_employee_calendar(employee: str, month: str | None = None) -> dict:
    if not frappe.has_permission("Employee", "read", doc=employee):
        frappe.throw("Not permitted to read this employee", frappe.PermissionError)
    month = month or getdate().strftime("%Y-%m")
    year, mon = (int(part) for part in month.split("-"))
    start = date(year, mon, 1)
    end = date(year, mon, _calendar.monthrange(year, mon)[1])
    today = getdate()

    holiday_list = frappe.db.get_value("Employee", employee, "holiday_list")
    holidays, weekly_off = {}, None
    if holiday_list:
        weekly_off = frappe.db.get_value("Holiday List", holiday_list, "weekly_off") or None
        for row in frappe.get_all(
            "Holiday",
            filters={"parent": holiday_list, "holiday_date": ["between", [start, end]]},
            fields=["holiday_date", "description"],
        ):
            holidays[str(row.holiday_date)] = row.description or "Holiday"

    attendance = {
        str(row.attendance_date): row
        for row in frappe.get_all(
            "Attendance",
            filters={"employee": employee, "docstatus": ["<", 2],
                     "attendance_date": ["between", [start, end]]},
            fields=["attendance_date", "status", "late_entry", "early_exit", "shift"],
        )
    }

    leave_days = {}
    for row in frappe.get_all(
        "Leave Application",
        filters={"employee": employee, "docstatus": 1, "from_date": ["<=", end], "to_date": [">=", start]},
        fields=["leave_type", "from_date", "to_date", "half_day"],
    ):
        day, last = getdate(row.from_date), getdate(row.to_date)
        while day <= last:
            if start <= day <= end:
                leave_days[day.isoformat()] = row.leave_type + (" (half)" if row.half_day else "")
            day += timedelta(days=1)

    shifts = {}
    for row in frappe.get_all(
        "Shift Assignment",
        filters={"employee": employee, "docstatus": 1, "start_date": ["<=", end]},
        fields=["shift_type", "start_date", "end_date"],
    ):
        day = getdate(row.start_date)
        last = min(getdate(row.end_date), end) if row.end_date else end
        while day <= last:
            if start <= day <= end:
                shifts[day.isoformat()] = row.shift_type
            day += timedelta(days=1)

    checkin_events = {}
    for row in frappe.db.sql(
        """
        SELECT time, log_type FROM `tabEmployee Checkin`
        WHERE employee = %(employee)s AND time >= %(start)s AND time < %(end)s
        ORDER BY time
        """,
        {"employee": employee, "start": start, "end": end + timedelta(days=1)},
        as_dict=True,
    ):
        checkin_events.setdefault(row.time.date(), []).append((row.time, row.log_type))
    checkin_summary = {}
    for day_key, events in checkin_events.items():
        ins = [moment for moment, log_type in events if log_type == "IN"]
        outs = [moment for moment, log_type in events if log_type == "OUT"]
        checkin_summary[day_key] = {
            "count": len(events),
            "in_time": min(ins).strftime("%H:%M") if ins else None,
            "out_time": max(outs).strftime("%H:%M") if outs else None,
        }
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekoff_index = weekdays.index(weekly_off) if weekly_off in weekdays else None

    days = []
    legend = {}
    day = start
    while day <= end:
        key = day.isoformat()
        att = attendance.get(key)
        category, detail = "No Record", ""
        if att and att.status in ("Present", "Half Day"):
            category = att.status
            flags = [name for name, flag in (("Late", att.late_entry), ("Early exit", att.early_exit)) if flag]
            if key in holidays:
                flags.append("worked on holiday/off day (%s)" % holidays[key])
            detail = ", ".join(flags)
        elif key in holidays:
            category, detail = "Holiday", holidays[key]
        elif key in leave_days:
            category, detail = "Leave", leave_days[key]
        elif att:
            category = att.status
            flags = [name for name, flag in (("Late", att.late_entry), ("Early exit", att.early_exit)) if flag]
            detail = ", ".join(flags)
        elif weekoff_index is not None and day.weekday() == weekoff_index:
            category = "Weekly Off"
        elif day > today:
            category = "Future"
        elif checkin_summary.get(day, {}).get("count"):
            category = "Punched Only"
            detail = "attendance not generated for this day"

        if category in ("Leave", "On Leave"):
            color = leave_color(detail or None)
            label = detail or category
        elif att and att.late_entry and category == "Present":
            color, label = LATE_COLOR, "Present (Late)"
        elif att and att.early_exit and category == "Present":
            color, label = EARLY_COLOR, "Present (Early exit)"
        else:
            color = BASE_COLORS.get(category, "#ffffff")
            label = category
        legend[label] = color

        summary = checkin_summary.get(day, {})
        days.append({
            "date": key, "day": day.day, "category": category, "label": label,
            "color": color, "detail": detail,
            "shift": shifts.get(key, ""), "checkins": int(summary.get("count") or 0),
            "in_time": summary.get("in_time"), "out_time": summary.get("out_time"),
        })
        day += timedelta(days=1)

    return {
        "employee": employee,
        "employee_name": frappe.db.get_value("Employee", employee, "employee_name"),
        "month": month,
        "holiday_list": holiday_list,
        "weekly_off": weekly_off,
        "today": today.isoformat(),
        "legend": legend,
        "days": days,
    }
