"""Flexible Daily Wage units around native Attendance and payroll semantics."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time
from typing import Any

import frappe
from frappe.utils import cint, flt, getdate

from workforce_suite.workforce_suite.pay_basis import DAILY
from workforce_suite.workforce_suite.company_context import assert_company_access


WORK_STATUSES = {"Present", "Half Day", "Work From Home"}
ABSENCE_STATUSES = {"Absent", "On Leave"}


def _v(row: Any, key: str, default=None):
    return row.get(key, default) if isinstance(row, dict) else getattr(row, key, default)


def calculate_flexible_work_units(working_hours, policy: dict[str, Any]) -> float:
    """Return capped base-pay units; no overtime money or unit is included."""
    if working_hours is None:
        raise ValueError("FLEX_WORKING_HOURS_REQUIRED")
    hours = flt(working_hours)
    standard = flt(policy.get("standard_paid_hours"))
    threshold = flt(policy.get("full_day_minimum_hours"))
    if hours < 0 or standard <= 0 or threshold <= 0 or threshold > standard:
        raise ValueError("FLEX_WORK_POLICY_INVALID")
    if not hours:
        return 0.0
    return round(min(1.0, 1.0 if hours >= threshold else hours / standard), 8)


def _matches_override(override, row, employee):
    if getdate(_v(override, "attendance_date") or _v(override, "operational_date")) != getdate(_v(row, "attendance_date")):
        return False
    branch = _v(row, "branch") or _v(employee, "branch")
    department = _v(row, "department") or _v(employee, "department")
    return (not _v(override, "branch") or _v(override, "branch") == branch) and (
        not _v(override, "department") or _v(override, "department") == department
    )


def apply_flexible_work_adjustments(
    native_units: float,
    attendance_rows: list[dict[str, Any]],
    policy: dict[str, Any],
    *,
    overrides=None,
    employee=None,
    holidays=(),
    half_day_fraction=0.5,
):
    """Adjust work-only days and leave all other native payroll units intact."""
    findings, delta = [], 0.0
    overrides = overrides or []
    holiday_dates = {getdate(day) for day in holidays}
    for row in attendance_rows:
        status = _v(row, "status")
        hours = _v(row, "working_hours")
        day = getdate(_v(row, "attendance_date"))
        if status in ABSENCE_STATUSES:
            if hours is not None and flt(hours) > 0:
                findings.append({"code": "FLEX_ATTENDANCE_STATUS_CONFLICT", "attendance": _v(row, "name")})
            continue
        if status not in WORK_STATUSES:
            continue
        if day in holiday_dates:
            continue
        if _v(row, "leave_type") or _v(row, "leave_application"):
            continue
        if hours is None or flt(hours) <= 0:
            findings.append({"code": "FLEX_WORKING_HOURS_REQUIRED", "attendance": _v(row, "name")})
            continue
        try:
            target = calculate_flexible_work_units(hours, policy)
        except ValueError as exc:
            findings.append({"code": str(exc), "attendance": _v(row, "name")})
            continue
        baseline = 1.0
        if status == "Half Day" and _v(row, "half_day_status") == "Absent":
            baseline = max(0.0, 1.0 - flt(half_day_fraction))
        matching = [
            item for item in overrides
            if status in {"Present", "Half Day"}
            and day not in holiday_dates
            and _matches_override(item, row, employee or {})
        ]
        if len(matching) > 1:
            findings.append({"code": "OPERATIONAL_DAY_OVERRIDE_CONFLICT", "attendance": _v(row, "name")})
            continue
        if matching:
            target = 1.0
        delta += target - baseline
    if findings:
        return {"status": "NEEDS_ATTENTION", "payable_units": flt(native_units), "findings": findings}
    return {"status": "READY", "payable_units": round(max(0.0, flt(native_units) + delta), 8), "findings": []}


def _overlaps(start_a, end_a, start_b, end_b):
    a0, b0 = getdate(start_a), getdate(start_b)
    a1 = getdate(end_a) if end_a else getdate("9999-12-31")
    b1 = getdate(end_b) if end_b else getdate("9999-12-31")
    return a0 <= b1 and b0 <= a1


def flexible_policy_scope_state(policy, contexts):
    """Return whether a rule matches none, some, or all reviewed contexts."""
    matches = [
        (not _v(policy, "branch") or _v(policy, "branch") == branch)
        and (not _v(policy, "department") or _v(policy, "department") == department)
        for branch, department in contexts
    ]
    if matches and all(matches):
        return "all"
    if any(matches):
        return "partial"
    return "outside"


def shift_assignment_covers_period(assignment, start, end):
    """Whether a submitted native assignment covers every requested date."""
    return (
        getdate(_v(assignment, "start_date")) <= getdate(start)
        and (
            not _v(assignment, "end_date")
            or getdate(_v(assignment, "end_date")) >= getdate(end)
        )
    )


def _policy_rows(company):
    cache = getattr(frappe.local, "workforce_flexible_work_policies", None)
    if cache is None:
        cache = {}
        frappe.local.workforce_flexible_work_policies = cache
    if company not in cache:
        cache[company] = frappe.get_all(
            "Workforce Flexible Work Policy",
            filters={"company": company, "docstatus": 1},
            fields=["name", "company", "branch", "department", "effective_from", "effective_to",
                    "standard_paid_hours", "full_day_minimum_hours", "flexible_shift_enabled"],
        )
    return cache[company]


def _override_rows(company, start, end):
    cache = getattr(frappe.local, "workforce_operational_day_overrides", None)
    if cache is None:
        cache = {}
        frappe.local.workforce_operational_day_overrides = cache
    key = (company, str(start), str(end))
    if key not in cache:
        rows = frappe.get_all(
            "Workforce Operational Day Override",
            filters={"company": company, "operational_date": ["between", [start, end]], "docstatus": 1},
            fields=["name", "company", "operational_date", "branch", "department", "preview_hash"],
        )
        cache[key] = [{**row, "attendance_date": row.operational_date} for row in rows]
    return cache[key]


def clear_flexible_work_caches():
    for key in (
        "workforce_flexible_work_policies",
        "workforce_operational_day_overrides",
        "workforce_operational_override_preview_validation",
    ):
        if hasattr(frappe.local, key):
            delattr(frappe.local, key)


def resolve_flexible_work_policy(employee, start, end, attendance_rows):
    employee_data = frappe.db.get_value("Employee", employee, ["company", "branch", "department"], as_dict=True)
    if not employee_data:
        return {"status": "NEEDS_ATTENTION", "code": "FLEX_WORK_POLICY_REVIEW_REQUIRED"}
    candidates = _policy_rows(employee_data.company)
    contexts = {
        (_v(row, "branch") or employee_data.branch, _v(row, "department") or employee_data.department)
        for row in attendance_rows
    } or {(employee_data.branch, employee_data.department)}
    overlapping = [
        row for row in candidates
        if _overlaps(row.effective_from, row.effective_to, start, end)
    ]
    scope_states = {row.name: flexible_policy_scope_state(row, contexts) for row in overlapping}
    candidates = [row for row in overlapping if scope_states[row.name] == "all"]
    partial_scope = [row for row in overlapping if scope_states[row.name] == "partial"]
    if partial_scope:
        return {
            "status": "NEEDS_ATTENTION",
            "code": "FLEX_WORK_POLICY_MID_PERIOD_CHANGE",
            "reason": "A scoped policy applies to only part of this Employee's establishment history.",
        }
    if not candidates:
        return {"status": "READY", "policy": None}
    covering = [
        row for row in candidates
        if getdate(row.effective_from) <= getdate(start)
        and (not row.effective_to or getdate(row.effective_to) >= getdate(end))
    ]
    if len(candidates) != 1 or len(covering) != 1:
        return {
            "status": "NEEDS_ATTENTION",
            "code": "FLEX_WORK_POLICY_MID_PERIOD_CHANGE",
            "reason": "One approved flexible-work policy must cover the full payroll period.",
        }
    return {"status": "READY", "policy": covering[0]}


def load_operational_overrides(company, start, end):
    cache = getattr(frappe.local, "workforce_operational_override_preview_validation", None)
    if cache is None:
        cache = {}
        frappe.local.workforce_operational_override_preview_validation = cache
    key = (company, str(start), str(end))
    if key not in cache:
        rows = _override_rows(company, start, end)
        from workforce_suite.workforce_suite.flexible_work_records import build_operational_day_override_preview
        for row in rows:
            preview = build_operational_day_override_preview(frappe._dict(row))
            row["preview_stale"] = (
                preview["status"] != "READY"
                or preview["attendance_hash"] != row.get("preview_hash")
            )
        cache[key] = rows
    return cache[key]


def _override_matches_work_rows(override, attendance_rows, employee, holidays):
    for row in attendance_rows:
        if _v(row, "status") not in {"Present", "Half Day"}:
            continue
        if _v(row, "leave_type") or _v(row, "leave_application"):
            continue
        day = getdate(_v(row, "attendance_date"))
        if day in holidays:
            continue
        if _matches_override(override, row, employee):
            return True
    return False


def apply_policy_to_daily_wage(employee, employee_data, start, end, attendance_rows, native):
    """Resolve an optional approved company policy and apply only its work-day delta."""
    if not attendance_rows:
        return native
    resolution = resolve_flexible_work_policy(employee, start, end, attendance_rows)
    if resolution["status"] != "READY":
        return {"status": resolution["status"], "reason": resolution.get("reason", resolution.get("code"))}
    overrides = load_operational_overrides(employee_data.company, start, end)
    overrides = [
        row for row in overrides
        if _override_matches_work_rows(
            row, attendance_rows, employee, native.get("holidays", ()),
        )
    ]
    policy = resolution.get("policy")
    if any(row.get("preview_stale") for row in overrides):
        return {"status": "NEEDS_ATTENTION", "reason": "Operational Day Override preview is stale; review and reapprove before payroll."}
    if not policy:
        if overrides:
            return {"status": "NEEDS_ATTENTION", "reason": "An operational-day override has no applicable approved flexible-work policy."}
        return native
    adjusted = apply_flexible_work_adjustments(
        native["payable_units"], attendance_rows, policy, overrides=overrides,
        employee=employee_data, holidays=native.get("holidays", ()),
        half_day_fraction=native.get("half_day_fraction", 0.5),
    )
    if adjusted["status"] != "READY":
        return {
            "status": adjusted["status"],
            "reason": "; ".join(item["code"] for item in adjusted["findings"]),
            "findings": adjusted["findings"],
        }
    return {**native, **adjusted, "flexible_work_policy": policy.name}


@frappe.whitelist()
def inspect_mass_early_release_candidates(
    company, from_date, to_date, minimum_headcount, minimum_percentage,
    clustering_window_minutes=30, scope_level="Branch",
):
    """Read-only detector with explicit thresholds and no automatic pay action."""
    assert_company_access(company, require_explicit_scope=True)
    rows = frappe.get_all(
        "Attendance",
        filters={"company": company, "attendance_date": ["between", [getdate(from_date), getdate(to_date)]], "docstatus": 1},
        fields=["employee", "attendance_date", "branch", "department", "status", "working_hours", "early_exit", "out_time"],
        order_by="attendance_date asc, branch asc, department asc",
    )
    return detect_mass_early_release_candidates(
        rows, minimum_headcount=int(minimum_headcount),
        minimum_percentage=float(minimum_percentage),
        clustering_window_minutes=int(clustering_window_minutes),
        scope_level=scope_level,
    )


@frappe.whitelist()
def preview_operational_day_override(company, operational_date, branch=None, department=None):
    assert_company_access(company, require_explicit_scope=True)
    from workforce_suite.workforce_suite.flexible_work_records import build_operational_day_override_preview
    return build_operational_day_override_preview(frappe._dict({
        "company": company, "operational_date": getdate(operational_date),
        "branch": branch, "department": department,
    }))


def detect_mass_early_release_candidates(
    attendance_rows,
    *,
    minimum_headcount: int,
    minimum_percentage: float,
    clustering_window_minutes: int,
    scope_level: str = "Branch",
):
    """Return read-only candidates and never create or submit an override."""
    if minimum_headcount < 1 or not 0 < minimum_percentage <= 1 or clustering_window_minutes < 0:
        raise ValueError("Provide explicit, valid detection thresholds.")
    if scope_level not in {"Branch", "Department"}:
        raise ValueError("scope_level must be Branch or Department.")
    groups = defaultdict(list)
    for row in attendance_rows:
        if _v(row, "status") in {"Present", "Half Day"}:
            group = (
                str(getdate(_v(row, "attendance_date"))),
                _v(row, "branch") or "",
                (_v(row, "department") or "") if scope_level == "Department" else "",
            )
            groups[group].append(row)
    results = []
    for (day, branch, department), rows in groups.items():
        present = {str(_v(row, "employee")) for row in rows}
        exits = []
        for row in rows:
            out = _v(row, "out_time")
            if not _v(row, "early_exit") or not out:
                continue
            if isinstance(out, datetime):
                minute = out.hour * 60 + out.minute
            elif isinstance(out, time):
                minute = out.hour * 60 + out.minute
            else:
                hour, minute_part, *_ = str(out)[-8:].split(":")
                minute = int(hour) * 60 + int(minute_part)
            exits.append((minute, str(_v(row, "employee"))))
        exits.sort()
        best, right = [], 0
        for left in range(len(exits)):
            right = max(right, left)
            while right < len(exits) and exits[right][0] - exits[left][0] <= clustering_window_minutes:
                right += 1
            cluster = exits[left:right]
            if len({employee for _, employee in cluster}) > len({employee for _, employee in best}):
                best = cluster
        affected = {employee for _, employee in best}
        ratio = len(affected) / len(present) if present else 0
        if len(affected) < minimum_headcount or ratio < minimum_percentage:
            continue
        values = sorted(value for value, _ in best)
        median = values[len(values) // 2]
        results.append({
            "code": "MASS_EARLY_RELEASE_CANDIDATE", "date": day,
            "scope_level": scope_level, "branch": branch or None,
            "department": department or None,
            "present_count": len(present), "affected_count": len(affected),
            "affected_ratio": ratio, "suggested_release_time": f"{median // 60:02d}:{median % 60:02d}",
            "creates_override": False,
        })
    return sorted(results, key=lambda row: (row["date"], row["branch"] or "", row["department"] or ""))


def native_shift_multiple_assignment_enabled():
    """Detect the installed native HRMS setting instead of a version assumption."""
    return bool(cint(frappe.db.get_single_value("HR Settings", "allow_multiple_shift_assignments")))


def inspect_flexible_shift_readiness(employee, from_date, to_date):
    employee_data = frappe.db.get_value("Employee", employee, ["company", "branch", "department"], as_dict=True)
    if not employee_data:
        return {"status": "NEEDS_ATTENTION", "findings": [{"code": "FLEX_WORK_POLICY_REVIEW_REQUIRED"}]}
    assert_company_access(employee_data.company, require_explicit_scope=True)
    resolution = resolve_flexible_work_policy(employee, getdate(from_date), getdate(to_date), [])
    policy = resolution.get("policy")
    if resolution["status"] != "READY" or not policy:
        return {"status": resolution["status"], "findings": [{"code": resolution.get("code", "FLEX_WORK_POLICY_NOT_CONFIGURED")}]}
    if not policy.flexible_shift_enabled:
        return {"status": "READY", "findings": []}
    if not native_shift_multiple_assignment_enabled():
        return {"status": "NEEDS_ATTENTION", "findings": [{"code": "MULTIPLE_SHIFT_ASSIGNMENTS_SETTING_REQUIRED"}]}
    allowed = frappe.get_all(
        "Workforce Flexible Shift Type",
        filters={"parent": policy.name, "parenttype": "Workforce Flexible Work Policy"},
        pluck="shift_type",
    )
    assignments = frappe.get_all(
        "Shift Assignment",
        filters={"employee": employee, "shift_type": ["in", allowed or [""]],
                 "docstatus": 1, "status": "Active", "start_date": ["<=", getdate(to_date)]},
        fields=["name", "shift_type", "start_date", "end_date"],
    )
    valid = [
        row for row in assignments
        if shift_assignment_covers_period(row, from_date, to_date)
    ]
    assigned_types = {row.shift_type for row in valid}
    missing = sorted(set(allowed) - assigned_types)
    findings = [{"code": "FLEX_SHIFT_ASSIGNMENT_REQUIRED", "shift_type": shift} for shift in missing]
    return {"status": "NEEDS_ATTENTION" if findings else "READY", "findings": findings}
