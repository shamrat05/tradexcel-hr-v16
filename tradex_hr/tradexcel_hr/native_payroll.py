"""Prepare native HRMS draft payroll without calculating payroll locally."""

from __future__ import annotations

import calendar
import hashlib
import json
from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate

from tradex_hr.tradexcel_hr.attendance_payroll_boundary import (
    _attendance_required_for_payroll,
    _employees_for_period,
    _row_value,
    _unapproved_overtime,
    current_attendance_period_hash,
    inspect_attendance_integrity,
)
from tradex_hr.tradexcel_hr.daily_wage_input import (
    DEFAULT_COMPONENT,
    _get_existing_input,
    calculate_daily_wage_input,
    create_daily_wage_input,
    inspect_daily_wage_structure,
)
from tradex_hr.tradexcel_hr.pay_basis import DAILY, MONTHLY, resolve_pay_basis
from tradex_hr.tradexcel_hr.wage_floor import (
	PASS_STATUSES as WAGE_FLOOR_PASS_STATUSES,
	inspect_wage_floor_for_employee,
	prepare_wage_floor_context,
)


def _dates(start_date: str | date, end_date: str | date) -> tuple[date, date]:
    start, end = getdate(start_date), getdate(end_date)
    if not start or not end or start > end:
        frappe.throw(_("Payroll dates are invalid"))
    return start, end


def _period_attendance_gate(company: str, start: date, end: date, employee_ids: list[str]):
    if not employee_ids and not _attendance_required_for_payroll():
        return []

    inspection = inspect_attendance_integrity(company, start, end, employee_ids)
    findings = [
        {
            "code": item.get("code", "BLOCKED_ATTENDANCE"),
            "employee": item.get("employee") or employee,
            "reason": item.get("reason", item.get("code", "Attendance needs review.")),
        }
        for item in inspection.get("blockers", [])
        for employee in ([item.get("employee")] if item.get("employee") else employee_ids)
    ]

    periods = frappe.get_all(
        "Tradexcel Attendance Period",
        filters={"company": company, "from_date": start, "to_date": end, "status": "Finalized"},
        fields=["name", "attendance_hash"],
    )
    if len(periods) != 1:
        if findings:
            return findings
        return [
            {
                "code": "BLOCKED_ATTENDANCE_PERIOD",
                "employee": employee,
                "reason": "Attendance review must be finalized once for this payroll month.",
            }
            for employee in employee_ids
        ]

    if current_attendance_period_hash(company, start, end) != _row_value(periods[0], "attendance_hash"):
        return findings + [
            {
                "code": "BLOCKED_ATTENDANCE_STALE",
                "employee": employee,
                "reason": "Finalized Attendance changed after review; reopen and finalize it again.",
            }
            for employee in employee_ids
        ]

    return findings


def inspect_native_payroll_readiness(
    company: str,
    start_date: str | date,
    end_date: str | date,
    employee_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Return one explainable outcome for every employee in native scope."""
    start, end = _dates(start_date, end_date)
    _validate_supported_scope(company, start, end, employee_ids)
    employees = _employees_for_period(company, start, end, employee_ids)
    ids = [_row_value(row, "name") for row in employees]
    wage_floor_context = prepare_wage_floor_context(company, start, end, ids)
    outcomes = {
        employee: {"employee": employee, "employee_data": row, "status": "READY"}
        for employee, row in ((_row_value(row, "name"), row) for row in employees)
    }

    def block(employee: str, code: str, reason: str):
        outcome = outcomes[employee]
        outcome.setdefault("findings", []).append({"code": code, "reason": reason})
        if outcome["status"] == "READY":
            outcome.update({"status": code, "reason": reason})

    for row in employees:
        employee = _row_value(row, "name")
        if _row_value(row, "status") not in {"Active", "Left"}:
            block(employee, "BLOCKED_EMPLOYMENT_STATUS", f"Employment status {_row_value(row, 'status')!r} has no approved payroll meaning.")
            continue
        basis = resolve_pay_basis(employee, start, end)
        outcomes[employee]["pay_basis"] = basis
        if basis.get("status") not in {MONTHLY, DAILY}:
            block(employee, "BLOCKED_PAY_BASIS", basis.get("reason", basis.get("status", "Pay basis is unresolved.")))

    required_attendance = [employee for employee, result in outcomes.items() if result.get("pay_basis", {}).get("status") == DAILY]
    if _attendance_required_for_payroll():
        required_attendance = ids
    for finding in _period_attendance_gate(company, start, end, required_attendance):
        employee = finding.get("employee")
        if employee in outcomes:
            block(employee, finding["code"], finding["reason"])

    for row in _unapproved_overtime(company, start, end, ids):
        employee = _row_value(row, "employee")
        if employee in outcomes:
            block(employee, "BLOCKED_OT", "Attendance overtime is not in a submitted native Overtime Slip.")

    for employee, outcome in outcomes.items():
        if outcome.get("pay_basis", {}).get("status") == DAILY:
            structure = inspect_daily_wage_structure(employee, start, end)
            if structure["status"] != "READY":
                outcome["daily_wage_input"] = structure
                block(employee, structure["status"], structure.get("reason", structure["status"]))
            elif outcome["status"] == "READY":
                result = calculate_daily_wage_input(employee, start, end)
                outcome["daily_wage_input"] = result
                if result.get("status") != "READY":
                    block(employee, result["status"], result.get("reason", result["status"]))

        floor = inspect_wage_floor_for_employee(
            employee,
            start,
            end,
            context=wage_floor_context,
            employee_data=outcome["employee_data"],
            pay_basis=outcome.get("pay_basis"),
        )
        outcome["wage_floor"] = floor
        if floor["status"] not in WAGE_FLOOR_PASS_STATUSES:
            reason = next((finding.get("message") for finding in floor.get("findings", []) if finding.get("severity") == "blocker"), floor["status"])
            block(employee, floor["status"], reason)

    blockers = [result for result in outcomes.values() if result["status"] != "READY"]
    if not employees:
        return {
            "company": company,
            "from_date": start,
            "to_date": end,
            "employee_count": 0,
            "ready_count": 0,
            "blocked_count": 1,
            "status": "BLOCKED",
            "outcomes": [],
            "blockers": [{"code": "BLOCKED_NO_EMPLOYEES", "reason": "No employees are in scope for this company and month."}],
        }

    return {
        "company": company,
        "from_date": start,
        "to_date": end,
        "employee_count": len(employees),
        "ready_count": len(employees) - len(blockers),
        "blocked_count": len(blockers),
        "status": "BLOCKED" if blockers else "READY",
        "outcomes": list(outcomes.values()),
    }


MANAGED_RUN_FIELD = "custom_tradex_run_key"
POPULATION_HASH_FIELD = "custom_tradex_population_hash"
ATTENDANCE_REVISION_FIELD = "custom_tradex_attendance_revision"
PAYROLL_MANAGER_ROLE = "Tradexcel Payroll Manager"
PAYROLL_SLIP_SUBMIT_ROLES = {PAYROLL_MANAGER_ROLE, "Tradexcel Payroll Approver"}


def _validate_supported_scope(company: str, start: date, end: date, employee_ids: list[str] | None) -> None:
    if start.day != 1 or end.year != start.year or end.month != start.month:
        frappe.throw(_("Managed payroll supports one complete calendar month."))
    if end.day != calendar.monthrange(start.year, start.month)[1]:
        frappe.throw(_("Managed payroll supports one complete calendar month."))
    if employee_ids and frappe.session.user != "Administrator" and not frappe.in_test:
        frappe.throw(_("Partial employee payroll is not supported. Prepare the full company population."))


def _managed_run_key(company: str, start: date, end: date) -> str:
    identity = f"{company}|{start:%Y-%m-%d}|{end:%Y-%m-%d}|Monthly"
    return f"TRAD-PAYROLL-{hashlib.sha256(identity.encode()).hexdigest()[:32]}"


def _attendance_revision(company: str, start: date, end: date, readiness: dict) -> str:
    daily = any(row.get("pay_basis", {}).get("status") == DAILY for row in readiness["outcomes"])
    if not daily and not _attendance_required_for_payroll():
        return ""
    periods = frappe.get_all(
        "Tradexcel Attendance Period",
        filters={"company": company, "from_date": start, "to_date": end, "status": "Finalized"},
        fields=["name", "revision", "attendance_hash"],
    )
    if len(periods) != 1:
        return ""
    period = periods[0]
    return f"{period.name}:r{period.revision}:{period.attendance_hash}"


def _daily_inputs_for_readiness(company: str, start: date, end: date, readiness: dict):
    daily = [row for row in readiness["outcomes"] if row.get("pay_basis", {}).get("status") == DAILY]
    if not daily:
        return [], []
    period = frappe.get_doc("Tradexcel Attendance Period", _finalized_period_name(company, start, end))
    planned, blockers = [], []
    for outcome in daily:
        employee = outcome["employee"]
        result = outcome.get("daily_wage_input") or calculate_daily_wage_input(employee, start, end)
        if result.get("status") != "READY":
            blockers.append({"employee": employee, "code": "BLOCKED_DAILY_WAGE_INPUT", "reason": result.get("reason", result.get("status"))})
            continue
        key = f"DAILY-WAGE:{period.name}:r{period.revision}:{employee}:{DEFAULT_COMPONENT}"
        existing = _get_existing_input(key)
        company_for_employee = _row_value(outcome["employee_data"], "company")
        if existing and (
            existing.docstatus == 2 or existing.disabled
            or existing.employee != employee or existing.company != company_for_employee
            or existing.salary_component != DEFAULT_COMPONENT
            or existing.ref_doctype != "Tradexcel Attendance Period"
            or existing.ref_docname != period.name or getdate(existing.payroll_date) != getdate(result["payroll_date"])
            or flt(existing.amount) != flt(result["amount"])
        ):
            blockers.append({
                "employee": employee,
                "code": "BLOCKED_DAILY_WAGE_INPUT_MISMATCH",
                "reason": "An existing derived Daily Wage input differs from current finalized Attendance or pay rate.",
            })
            continue
        planned.append({
            "employee": employee,
            "amount": result["amount"],
            "key": key,
            "period": period.name,
            "existing_name": existing.name if existing else None,
            "existing_docstatus": existing.docstatus if existing else None,
        })
    return planned, blockers


def _population_fingerprint(readiness: dict, daily_inputs: list[dict]) -> str:
    daily_amounts = {item["employee"]: item.get("amount") for item in daily_inputs}
    basis = [
        {
            "employee": row["employee"],
            "pay_basis": row.get("pay_basis"),
            "daily_amount": daily_amounts.get(row["employee"]),
        }
        for row in readiness["outcomes"]
    ]
    payload = json.dumps(basis, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _existing_payroll_entry(company: str, start: date, end: date):
    return frappe.get_all(
        "Payroll Entry",
        filters={"company": company, "start_date": start, "end_date": end},
        fields=[
            "name", "docstatus", "status", "salary_slips_created",
            MANAGED_RUN_FIELD, POPULATION_HASH_FIELD, ATTENDANCE_REVISION_FIELD,
        ],
        order_by="creation asc",
    )


def _block_existing_mismatch(readiness: dict, reason: str, entry_name: str | None = None):
    return {
        **readiness,
        "status": "BLOCKED_EXISTING_PAYROLL_MISMATCH",
        "blockers": [{
            "code": "BLOCKED_EXISTING_PAYROLL_MISMATCH",
            "payroll_entry": entry_name,
            "reason": reason,
        }],
    }


def _assert_preparation_authorized(company: str, employees: list[dict] | None = None) -> None:
    user = frappe.session.user
    roles = set(frappe.get_roles(user))
    privileged = user == "Administrator" or "System Manager" in roles
    if user == "Guest" or (not privileged and PAYROLL_MANAGER_ROLE not in roles):
        frappe.throw(
            _("Tradexcel Payroll Manager role is required to prepare payroll."),
            frappe.PermissionError,
        )

    frappe.has_permission("Payroll Entry", "create", throw=True)
    from tradex_hr.tradexcel_hr.company_context import assert_company_access

    assert_company_access(company, require_explicit_scope=True)

    for row in employees or []:
        if not frappe.has_permission("Employee", "read", _row_value(row, "name")):
            frappe.throw(
                _("You do not have access to every employee in this payroll company."),
                frappe.PermissionError,
            )


def _verify_managed_entry(doc) -> tuple[dict[str, Any], list[dict]]:
    start, end = _dates(doc.start_date, doc.end_date)
    _validate_supported_scope(doc.company, start, end, None)
    if doc.payroll_frequency != "Monthly" or any(doc.get(field) for field in ("branch", "department", "designation")):
        frappe.throw(_("Managed payroll requires full-company Monthly scope."))
    readiness = inspect_native_payroll_readiness(doc.company, start, end)
    if readiness["status"] != "READY":
        frappe.throw(_("Payroll readiness changed. Reopen Payroll Readiness and resolve the current blockers."))
    planned, blockers = _daily_inputs_for_readiness(doc.company, start, end, readiness)
    if blockers:
        frappe.throw(_("A current derived Daily Wage input is missing or mismatched. Reprepare payroll."))
    if doc.get(MANAGED_RUN_FIELD) != _managed_run_key(doc.company, start, end):
        frappe.throw(_("Payroll is not prepared. Open Payroll Readiness and prepare this period first."))
    if any(not row.get("existing_name") or row.get("existing_docstatus") != 1 for row in planned):
        frappe.throw(_("A prepared Daily Wage input is missing or not submitted. Reconcile payroll inputs before submitting."))
    if doc.get(POPULATION_HASH_FIELD) != _population_fingerprint(readiness, planned):
        frappe.throw(_("The employee population or current pay inputs changed after preparation. Prepare this period again."))
    if doc.get(ATTENDANCE_REVISION_FIELD) != _attendance_revision(doc.company, start, end, readiness):
        frappe.throw(_("Finalized Attendance changed after preparation. Reopen Payroll Readiness and prepare again."))
    if {row.employee for row in doc.employees} != {row["employee"] for row in readiness["outcomes"]}:
        frappe.throw(_("Payroll employee list no longer matches the full company population. Reprepare payroll."))
    return readiness, planned


def validate_payroll_entry_before_submit(doc, method=None) -> None:
    """Validate managed identity/readiness; never create derived money here."""
    if not doc.get(MANAGED_RUN_FIELD):
        frappe.throw(_("Payroll is not prepared. Open Payroll Readiness and prepare this period first."))
    if doc.workflow_state != "Tradexcel Payroll Pending Review":
        frappe.throw(_("Use Submit for Review to submit prepared payroll."))
    _verify_managed_entry(doc)


def _custom_payroll_role_requires_managed_slips() -> bool:
    """True when custom payroll roles are the user's only Salary Slip submit authority."""
    user = frappe.session.user
    if user == "Administrator":
        return False

    cache = getattr(frappe.local, "tradex_slip_submit_restrictions", None)
    if cache is None:
        cache = frappe.local.tradex_slip_submit_restrictions = {}
    if user in cache:
        return cache[user]

    roles = set(frappe.get_roles(user))
    restricted = bool(roles.intersection(PAYROLL_SLIP_SUBMIT_ROLES))
    if not restricted or "System Manager" in roles:
        cache[user] = False
        return False

    other_roles = roles - PAYROLL_SLIP_SUBMIT_ROLES
    if other_roles and frappe.get_all(
        "DocPerm",
        filters={
            "parent": "Salary Slip",
            "role": ["in", sorted(other_roles)],
            "submit": 1,
        },
        pluck="name",
        limit=1,
    ):
        # Preserve a legitimate native Salary Slip submit permission supplied by
        # another role. The custom payroll roles alone never grant this route.
        restricted = False

    cache[user] = restricted
    return restricted


def validate_salary_slip_before_submit(doc, method=None) -> None:
    """Keep custom payroll-role users on the approved native Payroll Entry path."""
    payroll_entry = doc.get("payroll_entry")
    custom_role_only = _custom_payroll_role_requires_managed_slips()

    if not payroll_entry:
        if custom_role_only:
            frappe.throw(_("Tradexcel payroll roles may submit Salary Slips only through an approved managed Payroll Entry."))
        return

    run_key = frappe.db.get_value("Payroll Entry", payroll_entry, MANAGED_RUN_FIELD)
    if not run_key:
        if custom_role_only:
            frappe.throw(_("Tradexcel payroll roles may submit Salary Slips only through an approved managed Payroll Entry."))
        return
    if not getattr(frappe.flags, "via_payroll_entry", False):
        frappe.throw(_("Submit managed Salary Slips from the approved Payroll Entry."))

    entry = frappe.get_doc("Payroll Entry", payroll_entry)
    if (
        entry.docstatus != 1
        or entry.workflow_state != "Tradexcel Payroll Approved"
        or not entry.salary_slips_created
    ):
        frappe.throw(_("Salary Slips are locked until Director approval of the managed Payroll Entry."))

    cache = getattr(frappe.local, "tradex_financial_readiness", None)
    if cache is None:
        cache = frappe.local.tradex_financial_readiness = {}
    if entry.name not in cache:
        from tradex_hr.tradexcel_hr.payroll_finalization import readiness_for_batch_submission

        cache[entry.name] = readiness_for_batch_submission(entry)
    result = cache[entry.name]
    if result["status"] != "READY":
        reason = result["blockers"][0]["reason"] if result["blockers"] else _("Financial checks need review.")
        frappe.throw(
            _("Salary Slips cannot be submitted because payroll financial readiness is blocked: {0}").format(reason),
            title=_("Payroll Financial Review Required"),
        )


def prepare_native_payroll(
    company: str,
    start_date: str | date,
    end_date: str | date,
    *,
    posting_date: str | date | None = None,
    employee_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Prepare a managed native Payroll Entry draft; native submit creates Salary Slips."""
    start, end = _dates(start_date, end_date)
    _assert_preparation_authorized(company)
    readiness = inspect_native_payroll_readiness(company, start, end, employee_ids)
    _assert_preparation_authorized(company, readiness["outcomes"])
    if readiness["status"] != "READY":
        return readiness

    run_key = _managed_run_key(company, start, end)
    existing = _existing_payroll_entry(company, start, end)
    managed = [row for row in existing if row.get(MANAGED_RUN_FIELD) == run_key]
    unmanaged = [
        row for row in existing
        if not row.get(MANAGED_RUN_FIELD) and int(_row_value(row, "docstatus") or 0) < 2
    ]
    if unmanaged:
        return _block_existing_mismatch(readiness, "An unmanaged Payroll Entry already exists for this company and month.", _row_value(unmanaged[0], "name"))
    if len(managed) > 1:
        return _block_existing_mismatch(readiness, "Multiple managed Payroll Entries exist for this identity.")
    if managed and int(_row_value(managed[0], "docstatus") or 0) == 2:
        return _block_existing_mismatch(readiness, "This managed payroll identity was already cancelled; reconcile before preparing another run.", _row_value(managed[0], "name"))

    daily_inputs, blockers = _daily_inputs_for_readiness(company, start, end, readiness)
    if blockers:
        return {**readiness, "status": "BLOCKED_DAILY_WAGE_INPUT", "blocked_count": len(blockers), "blockers": blockers}
    population_hash = _population_fingerprint(readiness, daily_inputs)
    attendance_revision = _attendance_revision(company, start, end, readiness)

    if managed:
        row = managed[0]
        doc = frappe.get_doc("Payroll Entry", _row_value(row, "name"))
        if (
            any(not item.get("existing_name") or item.get("existing_docstatus") != 1 for item in daily_inputs)
            or doc.company != company or doc.start_date != start or doc.end_date != end
            or doc.payroll_frequency != "Monthly"
            or doc.get(POPULATION_HASH_FIELD) != population_hash
            or doc.get(ATTENDANCE_REVISION_FIELD) != attendance_revision
            or {item.employee for item in doc.employees} != {item["employee"] for item in readiness["outcomes"]}
            or any(doc.get(field) for field in ("branch", "department", "designation"))
        ):
            return _block_existing_mismatch(readiness, "Managed Payroll Entry no longer matches current company, scope, employee population, Attendance revision, or pay inputs.", doc.name)
        if doc.status == "Failed":
            return {**readiness, "status": "NATIVE_SLIPS_FAILED", "payroll_entry": doc.name, "error_message": doc.error_message}
        if doc.status == "Queued":
            return {**readiness, "status": "NATIVE_SLIPS_QUEUED", "payroll_entry": doc.name}
        return {**readiness, "status": "PREPARED", "payroll_entry": doc.name}

    currency, payable_account, cost_center = frappe.get_cached_value(
        "Company", company,
        ["default_currency", "default_payroll_payable_account", "cost_center"],
    )
    if not currency or not payable_account:
        return {
            **readiness,
            "status": "BLOCKED_PAYROLL_ACCOUNT",
            "blockers": [{"code": "BLOCKED_PAYROLL_ACCOUNT", "reason": "Company currency/payroll payable account is not configured."}],
        }

    savepoint = "tradex_native_payroll_prepare"
    frappe.db.savepoint(savepoint)
    try:
        daily_results = [
            create_daily_wage_input(item["employee"], item["period"])
            for item in daily_inputs
        ]
        entry = frappe.get_doc({
            "doctype": "Payroll Entry",
            "company": company,
            "posting_date": posting_date or end,
            "start_date": start,
            "end_date": end,
            "payroll_frequency": "Monthly",
            "currency": currency,
            "exchange_rate": 1,
            "payroll_payable_account": payable_account,
            # HRMS Desk normally fetches this field from Company. Preparation
            # runs server-side, so set the same native default explicitly; the
            # accrual payable line uses Payroll Entry.cost_center.
            "cost_center": cost_center,
            "salary_slip_based_on_timesheet": 0,
            "validate_attendance": 1 if _attendance_required_for_payroll() else 0,
            "workflow_state": "Tradexcel Payroll Draft",
            MANAGED_RUN_FIELD: run_key,
            POPULATION_HASH_FIELD: population_hash,
            ATTENDANCE_REVISION_FIELD: attendance_revision,
            "employees": [
                {"employee": outcome["employee"], "employee_name": _row_value(outcome["employee_data"], "employee_name")}
                for outcome in readiness["outcomes"]
            ],
        })
        # Create permission was explicitly checked; bypass only to persist protected identity fields.
        entry.insert(ignore_permissions=True)
    except Exception:
        frappe.db.rollback(save_point=savepoint)
        raise
    return {
        **readiness,
        "status": "PREPARED",
        "payroll_entry": entry.name,
        "daily_inputs": daily_results,
        "salary_slips": [],
    }


def _finalized_period_name(company: str, start: date, end: date) -> str:
    rows = frappe.get_all(
        "Tradexcel Attendance Period",
        filters={"company": company, "from_date": start, "to_date": end, "status": "Finalized"},
        pluck="name",
    )
    if len(rows) != 1:
        frappe.throw(_("Exactly one finalized Attendance Period is required before Daily Wage preparation."))
    return rows[0]


def restrict_salary_slip_delete(doc, ptype, user=None, debug=False):
    """Allow native Payroll Entry cancellation to remove only its linked draft slips."""
    if ptype != "delete" or user == "Administrator":
        return True
    if doc.docstatus != 0 or not doc.payroll_entry:
        return False
    if not frappe.db.get_value("Payroll Entry", doc.payroll_entry, "custom_tradex_run_key"):
        return False
    entry = frappe.get_doc("Payroll Entry", doc.payroll_entry)
    return (
        entry.docstatus == 2
        and entry.workflow_state in ("Tradexcel Payroll Rejected", "Tradexcel Payroll Cancelled")
        and bool({"Tradexcel Payroll Approver", "Tradexcel Owner/Director"} & set(frappe.get_roles(user)))
    )
