"""Operator-facing payroll readiness report and guarded actions."""

from __future__ import annotations

import calendar
from datetime import date

import frappe
from frappe import _
from frappe.utils import getdate, today

from tradex_hr.tradexcel_hr.attendance_payroll_boundary import (
    inspect_attendance_integrity,
    _employees_for_period,
    _row_value,
)
from tradex_hr.tradexcel_hr.company_context import resolve_company
from tradex_hr.tradexcel_hr.native_payroll import (
    DAILY,
    MANAGED_RUN_FIELD,
    _existing_payroll_entry,
    _managed_run_key,
    inspect_native_payroll_readiness,
    prepare_native_payroll,
)
from tradex_hr.tradexcel_hr.pay_basis import resolve_pay_basis
from tradex_hr.tradexcel_hr.daily_wage_input import inspect_daily_wage_structure


REPORT_NAME = "Tradexcel Payroll Readiness"
PAYROLL_MANAGER_ROLE = "Tradexcel Payroll Manager"


def _assert_company_access(company: str) -> None:
    from tradex_hr.tradexcel_hr.company_context import assert_company_access

    assert_company_access(company, require_explicit_scope=True)


def _assert_employee_scope(rows: list[dict]) -> None:
    for row in rows:
        employee = _row_value(row, "name") if _row_value(row, "name") else row.get("employee")
        if employee and not frappe.has_permission("Employee", "read", employee):
            frappe.throw(_("You do not have access to every employee in this payroll company."), frappe.PermissionError)


def _report_period(filters: dict | None) -> tuple[str, date, date]:
    filters = frappe._dict(filters or {})
    company = resolve_company(filters)
    _assert_company_access(company)
    month = getdate(filters.get("payroll_month") or today())
    start = date(month.year, month.month, 1)
    end = date(month.year, month.month, calendar.monthrange(month.year, month.month)[1])
    return company, start, end


def _friendly_problem(findings: list[dict], outcome: dict) -> str:
    messages = []
    for finding in findings:
        code, reason = finding["code"], finding.get("reason", "")
        if code == "ATTENDANCE_UNMARKED":
            count = reason.split("found ", 1)[-1].split(" unmarked", 1)[0] if "found " in reason else ""
            message = f"{count} attendance day(s) need review" if count.isdigit() else "Attendance days need review"
        elif code == "BLOCKED_ATTENDANCE_PERIOD":
            message = "Attendance review is not finalized for this month"
        elif code == "BLOCKED_ATTENDANCE_STALE":
            message = "Attendance changed after review; finalize it again"
        elif code == "BLOCKED_PAY_BASIS" and "No submitted Salary Structure Assignment" in reason:
            message = f"No salary assignment applies on {outcome.get('period_start')}"
        elif code == "BLOCKED_UNSAFE_STRUCTURE":
            message = "Current Daily Wage structure can calculate the wrong amount; a new effective-dated structure is required"
        elif code == "BLOCKED_MISSING_BASE":
            message = "Daily Wage rate is missing from the salary assignment"
        elif code == "ATTENDANCE_REQUEST_PENDING":
            message = "Attendance correction request needs review"
        elif code == "BLOCKED_OT":
            message = "Overtime needs a submitted native Overtime Slip"
        else:
            message = reason or code.replace("_", " ").capitalize()
        if message not in messages:
            messages.append(message)
    if not messages:
        return ""
    if len(messages) == 1:
        return messages[0]
    return f"{messages[0]} (+ {len(messages) - 1} more issue)"


def _action_kinds(findings: list[dict]) -> str:
    codes = {row.get("code") for row in findings}
    actions = []
    if codes & {"ATTENDANCE_UNMARKED", "BLOCKED_ATTENDANCE", "BLOCKED_ATTENDANCE_PERIOD",
                "BLOCKED_ATTENDANCE_STALE", "ATTENDANCE_REQUEST_PENDING"}:
        actions.extend(("attendance", "attendance_requests"))
    if any(
        row.get("code") == "BLOCKED_PAY_BASIS"
        and "No submitted Salary Structure Assignment" in row.get("reason", "")
        for row in findings
    ):
        actions.append("salary_assignments")
    if "BLOCKED_UNSAFE_STRUCTURE" in codes:
        actions.append("migration")
    return "|".join(actions)


def _financial_action_kinds(findings: list[dict]) -> str:
    codes = {row.get("code") for row in findings}
    actions = []
    if codes & {"TAX_SLAB_MISSING", "TAX_SLAB_UNAPPROVED"}:
        actions.append("tax_slabs")
    if "TAX_EXCEPTION_REVIEW_REQUIRED" in codes:
        actions.append("policy_exceptions")
    if "TAX_PERIOD_MISSING" in codes:
        actions.append("payroll_periods")
    if "TAX_ASSIGNMENT_MISSING" in codes:
        actions.append("salary_assignments")
    if codes & {"TAX_COMPONENT_MISSING", "COMPONENT_ACCOUNT_MISSING"}:
        actions.append("salary_components")
    if "PAYROLL_PAYABLE_INVALID" in codes:
        actions.append("payroll_payable")
    if any(row.get("code") == "ACCOUNTING_DIMENSION_MISSING" and row.get("reference") == "Cost Center" for row in findings):
        actions.append("cost_centers")
    if any(row.get("code") == "ACCOUNTING_DIMENSION_MISSING" and row.get("reference") != "Cost Center" for row in findings):
        actions.append("accounting_dimensions")
    if codes & {"NEGATIVE_NET_PAY", "SLIP_TOTAL_MISMATCH", "DRAFT_SLIP_UNIVERSE_MISMATCH", "DRAFT_SLIP_MISSING"}:
        actions.append("salary_slip")
    return "|".join(actions)


def execute(filters: dict | None = None):
    """Return exactly one human-readable row per in-scope employee."""
    company, start, end = _report_period(filters)
    readiness = inspect_native_payroll_readiness(company, start, end)
    _assert_employee_scope(readiness["outcomes"])
    columns = [
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 125},
        {"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 190},
        {"label": _("Pay Basis"), "fieldname": "pay_basis", "fieldtype": "Data", "width": 115},
        {"label": _("Status"), "fieldname": "status_label", "fieldtype": "Data", "width": 130},
        {"label": _("Problem"), "fieldname": "problem", "fieldtype": "Data", "width": 360},
        {"label": _("Actions"), "fieldname": "actions", "fieldtype": "Data", "width": 245},
        {"label": _("Financial Status"), "fieldname": "financial_status", "fieldtype": "Data", "width": 125},
        {"label": _("Financial Review"), "fieldname": "financial_review", "fieldtype": "Data", "width": 300},
        {"label": _("Financial Result"), "fieldname": "financial_result", "fieldtype": "Data", "width": 340},
        {"label": _("Component Adjustments"), "fieldname": "component_adjustments", "fieldtype": "Data", "width": 260},
        {"label": _("Financial Actions"), "fieldname": "financial_action_kinds", "fieldtype": "Data", "width": 240},
        {"label": _("Salary Slip"), "fieldname": "financial_salary_slip", "fieldtype": "Data", "hidden": 1},
        {"label": _("Salary Component"), "fieldname": "financial_component", "fieldtype": "Data", "hidden": 1},
        {"label": _("Payroll Account"), "fieldname": "financial_account", "fieldtype": "Data", "hidden": 1},
        {"label": _("Previous Net"), "fieldname": "previous_net", "fieldtype": "Currency", "width": 125},
        {"label": _("Net Change"), "fieldname": "net_variance", "fieldtype": "Currency", "width": 125},
        {"label": _("Change %"), "fieldname": "net_variance_percent", "fieldtype": "Percent", "width": 95},
        {"label": _("Action Types"), "fieldname": "action_kinds", "fieldtype": "Data", "hidden": 1},
        {"label": _("Period Start"), "fieldname": "period_start", "fieldtype": "Date", "hidden": 1},
        {"label": _("Period End"), "fieldname": "period_end", "fieldtype": "Date", "hidden": 1},
    ]
    rows = []
    for outcome in readiness["outcomes"]:
        findings = list(outcome.get("findings") or [])
        if not findings and outcome.get("reason"):
            findings.append({"code": outcome["status"], "reason": outcome["reason"]})
        basis = outcome.get("pay_basis") or {}
        basis_label = {
            "Monthly Salary": _("Monthly"),
            DAILY: _("Daily Wage"),
        }.get(basis.get("status"), _("Needs review"))
        rows.append({
            "company": company,
            "employee": outcome["employee"],
            "employee_name": _row_value(outcome["employee_data"], "employee_name"),
            "pay_basis": basis_label,
            "status_label": _("READY") if outcome["status"] == "READY" else _("NEEDS ATTENTION"),
            "problem": _friendly_problem(findings, {"period_start": start}),
            "financial_status": "-",
            "financial_review": "",
            "financial_result": "",
            "component_adjustments": "",
            "financial_action_kinds": "",
            "financial_salary_slip": "",
            "financial_component": "",
            "financial_account": "",
            "previous_net": None,
            "net_variance": None,
            "net_variance_percent": None,
            "action_kinds": _action_kinds(findings),
            "period_start": start,
            "period_end": end,
        })
    ready = readiness["ready_count"]
    blocked = readiness["blocked_count"]
    run_rows = _existing_payroll_entry(company, start, end)
    managed_key = _managed_run_key(company, start, end)
    managed = next((row for row in run_rows if row.get(MANAGED_RUN_FIELD) == managed_key), None)
    unmanaged = any(
        not row.get(MANAGED_RUN_FIELD) and int(_row_value(row, "docstatus") or 0) < 2
        for row in run_rows
    )
    entry_status = "Not prepared"
    slip_status = "Not started"
    entry_name = ""
    if unmanaged:
        entry_status = "Unmanaged entry needs review"
    elif managed:
        entry_name = _row_value(managed, "name")
        entry_status = "Cancelled" if int(_row_value(managed, "docstatus") or 0) == 2 else _row_value(managed, "status")
        if entry_status == "Queued":
            slip_status = "Queued"
        elif entry_status == "Failed":
            slip_status = "Failed"
        elif _row_value(managed, "salary_slips_created"):
            slip_status = "Complete"

    summary = [
        {"label": _("Employees"), "value": readiness["employee_count"], "indicator": "blue"},
        {"label": _("Ready"), "value": ready, "indicator": "green"},
        {"label": _("Need attention"), "value": blocked, "indicator": "orange" if blocked else "green"},
        {"label": _("Salary Slip creation"), "value": slip_status, "indicator": "orange" if slip_status in {"Queued", "Failed"} else "green"},
        {"label": _("Managed Payroll Entry"), "value": entry_name or entry_status, "indicator": "blue"},
    ]
    if managed and int(_row_value(managed, "docstatus") or 0) == 1 and _row_value(managed, "salary_slips_created"):
        from tradex_hr.tradexcel_hr.financial_readiness import inspect_payroll_financial_readiness

        financial = inspect_payroll_financial_readiness(_row_value(managed, "name"))
        financial_by_employee = {row["employee"]: row for row in financial["slips"]}
        employee_blockers = {}
        global_blocker = next((row for row in financial["blockers"] if not row.get("employee")), None)
        for blocker in financial["blockers"]:
            if blocker.get("employee"):
                employee_blockers.setdefault(blocker["employee"], []).append(blocker["reason"])
        for row in rows:
            outcome = financial_by_employee.get(row["employee"])
            applicable_findings = [item for item in financial["blockers"]
                                   if not item.get("employee") or item.get("employee") == row["employee"]]
            applicable_findings.extend(financial["warnings"])
            if not outcome:
                row["financial_status"] = _("Missing slip")
                row["financial_review"] = _("No draft Salary Slip was found for this employee.")
                applicable_findings.append({"code": "DRAFT_SLIP_MISSING"})
            elif employee_blockers.get(row["employee"]):
                row["financial_status"] = _("BLOCKED")
                row["financial_review"] = employee_blockers[row["employee"]][0]
            elif global_blocker:
                row["financial_status"] = _("BLOCKED")
                row["financial_review"] = global_blocker["reason"]
            elif financial["warnings"]:
                row["financial_status"] = _("REVIEW")
                row["financial_review"] = financial["warnings"][0]["reason"]
            else:
                row["financial_status"] = _(outcome["status"])
                row["financial_review"] = ""
            if outcome:
                row["financial_salary_slip"] = outcome["salary_slip"]
                row["financial_result"] = _("Gross {0} · deductions {1} · net {2} · tax {3}").format(
                    outcome["gross"], outcome["deductions"], outcome["net"], outcome["income_tax"]
                )
                row["previous_net"] = outcome.get("previous_net")
                row["net_variance"] = outcome.get("net_variance")
                row["net_variance_percent"] = outcome.get("net_variance_percent")
                row["component_adjustments"] = "; ".join(
                    "{0}: {1} ({2}){3}".format(
                        item["component"], item["action"], item["source"],
                        " = {0:.2f}".format(item["amount"]) if item.get("amount") is not None else "",
                    )
                    for item in outcome.get("component_exceptions", [])
                )
            row["financial_action_kinds"] = _financial_action_kinds(applicable_findings)
            row["financial_component"] = next(
                (item.get("reference") for item in applicable_findings
                 if item.get("code") == "COMPONENT_ACCOUNT_MISSING" and item.get("reference")),
                "",
            )
            row["financial_account"] = next(
                (item.get("reference") for item in applicable_findings
                 if item.get("code") == "PAYROLL_PAYABLE_INVALID" and item.get("reference")),
                "",
            )
        summary.extend([
            {"label": _("Financial review"),
             "value": _("READY WITH WARNINGS") if financial["status"] == "READY" and financial["warnings"]
             else (_("READY") if financial["status"] == "READY" else _("NEEDS REVIEW")),
             "indicator": "orange" if financial["warnings"] or financial["status"] != "READY" else "green"},
            {"label": _("Draft Salary Slips"), "value": financial["salary_slip_count"], "indicator": "blue"},
            {"label": _("Gross / Deductions / Net"),
             "value": "{0} / {1} / {2}".format(financial["totals"]["gross"], financial["totals"]["deductions"], financial["totals"]["net"]),
             "indicator": "blue"},
            {"label": _("Daily Wage / Overtime / Tax"),
             "value": "{0} / {1} / {2}".format(financial["totals"]["daily_wage"], financial["totals"]["overtime"], financial["totals"]["income_tax"]),
             "indicator": "blue"},
        ])

    message = _("{0} Payroll").format(start.strftime("%B %Y"))
    if managed and "financial" in locals() and financial["blockers"]:
        message += " · " + financial["blockers"][0]["reason"]
    if slip_status == "Failed":
        message += " · " + _("Salary Slip creation failed. Open the Payroll Entry for native retry.")
    return columns, rows, message, None, summary


def _require_payroll_manager(company: str) -> None:
    if frappe.session.user in ("Guest", None):
        frappe.throw(_("Sign in with a named payroll account."), frappe.PermissionError)
    roles = set(frappe.get_roles())
    if frappe.session.user != "Administrator" and not roles.intersection(
        {PAYROLL_MANAGER_ROLE, "System Manager"}
    ):
        frappe.throw(_("Tradexcel Payroll Manager role is required for this action."), frappe.PermissionError)
    _assert_company_access(company)


@frappe.whitelist()
def prepare_payroll(company: str, payroll_month: str):
    """Recalculate readiness and prepare the native draft Payroll Entry."""
    _require_payroll_manager(company)
    company, start, end = _report_period({"company": company, "payroll_month": payroll_month})
    result = prepare_native_payroll(company, start, end)
    if result.get("status") != "PREPARED":
        return {
            "status": result.get("status"),
            "payroll_entry": result.get("payroll_entry"),
            "blockers": result.get("blockers", []),
            "ready_count": result.get("ready_count", 0),
            "blocked_count": result.get("blocked_count", 0),
            "error_message": result.get("error_message"),
        }
    return {"status": "PREPARED", "payroll_entry": result["payroll_entry"]}


@frappe.whitelist()
def get_daily_wage_migration_preview(company: str, payroll_month: str, effective_date: str | None = None):
    """Return a read-only migration plan; it never creates structures or assignments."""
    _require_payroll_manager(company)
    company, start, end = _report_period({"company": company, "payroll_month": payroll_month})
    effective = getdate(effective_date) if effective_date else None
    employees = _employees_for_period(company, start, end, None)
    _assert_employee_scope(employees)
    daily_candidates = []
    for employee_row in employees:
        employee = _row_value(employee_row, "name")
        basis = resolve_pay_basis(employee, effective or start)
        if basis.get("status") in (DAILY, "UNRESOLVED", "CONFLICT", "MID_PERIOD_CHANGE"):
            daily_candidates.append((employee_row, basis))

    ids = [_row_value(row, "name") for row, _basis in daily_candidates]
    inspection = inspect_attendance_integrity(company, start, end, ids)
    attendance_by_employee = {}
    for finding in inspection.get("blockers", []):
        employee = finding.get("employee")
        if employee:
            attendance_by_employee.setdefault(employee, []).append(finding.get("reason", finding.get("code")))

    later_assignments = {}
    if effective:
        conflicts = frappe.get_all(
            "Salary Structure Assignment",
            filters={"employee": ["in", ids], "from_date": [">=", effective], "docstatus": 1},
            fields=["employee", "name", "salary_structure", "from_date"],
        ) if ids else []
        for row in conflicts:
            later_assignments.setdefault(_row_value(row, "employee"), []).append(row)

    rows = []
    for employee_row, basis in daily_candidates:
        employee = _row_value(employee_row, "name")
        reasons = list(attendance_by_employee.get(employee, []))
        conflicts = later_assignments.get(employee, [])
        if basis.get("status") != DAILY:
            reasons.append(basis.get("reason", "Pay basis needs review."))
        else:
            structure = inspect_daily_wage_structure(employee, effective or start)
            if structure.get("status") != "READY":
                reasons.append(structure.get("reason", "Daily Wage structure needs review."))
        same_day = [row for row in conflicts if getdate(_row_value(row, "from_date")) == effective]
        later = [row for row in conflicts if getdate(_row_value(row, "from_date")) > effective]
        if same_day:
            reasons.append("A submitted Salary Structure Assignment already starts on the proposed effective date.")
        if later:
            reasons.append("A later submitted Salary Structure Assignment may supersede the proposed structure.")
        rows.append({
            "employee": employee,
            "employee_name": _row_value(employee_row, "employee_name"),
            "current_assignment": basis.get("assignment") or "",
            "current_structure": basis.get("salary_structure") or "",
            "current_rate": basis.get("base"),
            "current_basis": basis.get("status", "UNRESOLVED"),
            "requested_effective_date": effective,
            "conflicts": "; ".join(reasons),
        })

    return {
        "status": "PREVIEW" if effective else "DECISION_REQUIRED",
        "effective_date": effective,
        "employee_count": len(rows),
        "conflict_count": sum(bool(row["conflicts"]) for row in rows),
        "proposed_structure": {
            "name": _("New effective-dated Daily Wage structure (name to be approved)"),
            "pay_basis": DAILY,
            "components": [
                {"component": "Daily Wage", "amount": 0, "depends_on_payment_days": 0},
                {"component": "Overtime Pay", "amount": 0, "depends_on_payment_days": 0},
            ],
        },
        "rows": rows,
    }
