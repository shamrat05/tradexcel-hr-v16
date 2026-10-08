"""Scoped attendance-setting exceptions: pure matcher/calculator plus loader/doc event.

Settings follow the payroll pattern: a named setting with a numeric value.
Ignore settings clear flags; grace settings recompute flags from the linked
shift timing and the attendance punch times.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

import frappe
from frappe.utils import getdate

from workforce_suite.workforce_suite.component_exceptions import (
    branch_scope_map,
    department_scope_map,
    expand_scope,
    scope_match,
)


ATTENDANCE_SETTINGS = (
    "Ignore Late Marking",
    "Ignore Early Exit",
    "Ignore Late and Early Exit",
    "Late Grace Minutes",
    "Early Exit Grace Minutes",
)


def _in_window(rule, day):
    if rule.get("effective_from") and getdate(rule["effective_from"]) > day:
        return False
    if rule.get("effective_to") and getdate(rule["effective_to"]) < day:
        return False
    return True


def _rank(rule):
    # Same org hierarchy as component rules: employee > department/designation > branch.
    weight = 0
    if rule.get("department_scope"):
        weight += 10
    if rule.get("designation"):
        weight += 10
    if rule.get("branch_scope"):
        weight += 1
    return (
        1 if rule.get("employee") else 0,
        weight,
        -len(rule.get("branch_scope") or []) - len(rule.get("department_scope") or []),
    )


def _as_time(value):
    if value is None:
        return None
    if isinstance(value, timedelta):
        seconds = int(value.total_seconds()) % 86400
        return time(seconds // 3600, (seconds % 3600) // 60, seconds % 60)
    if isinstance(value, time):
        return value
    return time.fromisoformat(str(value)[:8])


def is_late(shift_start, in_time, grace_minutes):
    """True when the punch is after shift start plus grace. Both are pure inputs."""
    if not shift_start or not in_time:
        return None
    start = datetime.combine(in_time.date(), _as_time(shift_start))
    return in_time > start + timedelta(minutes=float(grace_minutes or 0))


def is_early_exit(shift_end, out_time, grace_minutes):
    """True when the punch is before shift end minus grace. Overnight shifts are skipped."""
    if not shift_end or not out_time:
        return None
    end_time = _as_time(shift_end)
    if end_time <= _as_time("00:00:01") or end_time <= _as_time("06:00"):
        return None  # overnight shift boundary: not safely comparable on one date
    end = datetime.combine(out_time.date(), end_time)
    return out_time < end - timedelta(minutes=float(grace_minutes or 0))


def resolve_attendance_settings(employee, day, rules):
    """Return setting -> winning rule, resolved per setting with conflict detection."""
    day = getdate(day)
    by_setting = {}
    for rule in rules:
        if not _in_window(rule, day) or not scope_match(employee, rule):
            continue
        by_setting.setdefault(rule.get("attendance_setting"), []).append(rule)
    winners = {}
    for setting, candidates in by_setting.items():
        top_rank = max(_rank(rule) for rule in candidates)
        top = [rule for rule in candidates if _rank(rule) == top_rank]
        values = {str(rule.get("attendance_value") or "") for rule in top}
        if len(values) > 1:
            raise ValueError(
                f"Conflicting {setting} rules: " + ", ".join(sorted(rule["name"] for rule in top))
            )
        winners[setting] = top[0]
    return winners


def apply_attendance_flags(doc, employee, rules, shift_times=None):
    settings = resolve_attendance_settings(employee, doc.attendance_date, rules)
    if not settings:
        return False
    changed = False
    ignore_late = "Ignore Late Marking" in settings or "Ignore Late and Early Exit" in settings
    ignore_early = "Ignore Early Exit" in settings or "Ignore Late and Early Exit" in settings

    if ignore_late:
        if doc.late_entry:
            doc.late_entry = 0
            changed = True
    elif "Late Grace Minutes" in settings and shift_times:
        grace = settings["Late Grace Minutes"].get("attendance_value") or 0
        computed = is_late(shift_times.get("start_time"), doc.in_time, grace)
        if computed is not None and int(bool(doc.late_entry)) != int(computed):
            doc.late_entry = int(computed)
            changed = True

    if ignore_early:
        if doc.early_exit:
            doc.early_exit = 0
            changed = True
    elif "Early Exit Grace Minutes" in settings and shift_times:
        grace = settings["Early Exit Grace Minutes"].get("attendance_value") or 0
        computed = is_early_exit(shift_times.get("end_time"), doc.out_time, grace)
        if computed is not None and int(bool(doc.early_exit)) != int(computed):
            doc.early_exit = int(computed)
            changed = True
    return changed


def build_attendance_rule(source, branch_map, department_map, include_children=True):
    rule = {
        "name": source.get("name"),
        "company": source.get("company"),
        "employee": source.get("employee"),
        "designation": source.get("designation"),
        "attendance_setting": source.get("attendance_setting"),
        "attendance_value": source.get("attendance_value"),
        "effective_from": source.get("effective_from"),
        "effective_to": source.get("effective_to"),
    }
    if include_children:
        rule["branch_scope"] = expand_scope(source.get("branch"), branch_map)
        rule["department_scope"] = expand_scope(source.get("department"), department_map)
    else:
        rule["branch_scope"] = [source.get("branch")] if source.get("branch") else None
        rule["department_scope"] = [source.get("department")] if source.get("department") else None
    return rule


def _load(company):
    rows = frappe.get_all(
        "Workforce Policy Exception",
        filters={"docstatus": 1, "company": company, "exception_type": "Attendance"},
        fields=["name", "company", "employee", "designation", "attendance_setting",
                "attendance_value", "effective_from", "effective_to", "branch",
                "department", "include_child_scope"],
    )
    if not rows:
        return []
    branch_map, department_map = branch_scope_map(), department_scope_map()
    return [
        build_attendance_rule(row, branch_map, department_map,
                              include_children=bool(row.get("include_child_scope", 1)))
        for row in rows
    ]


def load_attendance_rules(company):
    cache = getattr(frappe.local, "workforce_attendance_rules", None)
    if cache is None:
        cache = {}
        frappe.local.workforce_attendance_rules = cache
    if company not in cache:
        cache[company] = _load(company)
    return cache[company]


def sync_scope_fields(doc, method=None):
    """Keep Attendance.branch/department derived from the employee (never hand-maintained)."""
    if not doc.employee:
        return
    target = frappe.db.get_value("Employee", doc.employee, ["branch", "department"], as_dict=True)
    if not target:
        return
    if target.branch and doc.get("branch") != target.branch:
        doc.branch = target.branch
    if target.department and doc.get("department") != target.department:
        doc.department = target.department


def apply_to_attendance(doc, method=None):
    """Doc event: apply ignore/grace settings to attendance records in scope."""
    if not doc.employee or not doc.attendance_date or not doc.company:
        return
    rules = load_attendance_rules(doc.company)
    if not rules:
        return
    employee = frappe.db.get_value(
        "Employee", doc.employee,
        ["name", "company", "branch", "department", "designation"], as_dict=True,
    )
    if not employee:
        return
    shift_times = None
    if doc.shift:
        shift_times = frappe.db.get_value("Shift Type", doc.shift,
                                          ["start_time", "end_time"], as_dict=True)
    apply_attendance_flags(doc, employee, rules, shift_times)
