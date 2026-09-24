"""Approval and preview records for flexible work and exceptional paid days."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime

from tradex_hr.tradexcel_hr.company_context import assert_company_access
from tradex_hr.tradexcel_hr.flexible_work import calculate_flexible_work_units


APPROVER_ROLE = "Tradexcel Owner/Director"
PAY_APPROVER_ROLE = "Tradexcel Payroll Approver"


def _get(row, field, default=None):
    return row.get(field, default) if isinstance(row, dict) else getattr(row, field, default)


def _active_policies(company):
    return frappe.get_all(
        "Tradexcel Flexible Work Policy",
        filters={"company": company, "docstatus": 1},
        fields=["name", "company", "branch", "department", "effective_from", "effective_to",
                "standard_paid_hours", "full_day_minimum_hours"],
    )


def _policy_for_row(policies, row):
    day = getdate(row.attendance_date)
    branch, department = row.branch, row.department
    return [
        policy for policy in policies
        if getdate(policy.effective_from) <= day
        and (not policy.effective_to or getdate(policy.effective_to) >= day)
        and (not policy.branch or policy.branch == branch)
        and (not policy.department or policy.department == department)
    ]


def _native_holiday_context(employee_names, day):
    """Resolve holiday dates through ERPNext's employee holiday-list API."""
    from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee

    if frappe.get_hooks("employee_holiday_list"):
        employee_lists = {
            employee: get_holiday_list_for_employee(employee, raise_exception=False, as_on=day)
            for employee in employee_names
        }
    else:
        employees = frappe.get_all(
            "Employee", filters={"name": ["in", employee_names]},
            fields=["name", "holiday_list", "company"],
        ) if employee_names else []
        companies = sorted({row.company for row in employees if row.company})
        defaults = {
            row.name: row.default_holiday_list
            for row in frappe.get_all(
                "Company", filters={"name": ["in", companies]},
                fields=["name", "default_holiday_list"],
            )
        } if companies else {}
        employee_lists = {
            row.name: row.holiday_list or defaults.get(row.company)
            for row in employees
        }
    holiday_lists = sorted({holiday_list for holiday_list in employee_lists.values() if holiday_list})
    holiday_list_names = set()
    if holiday_lists:
        holiday_list_names = {
            row.parent for row in frappe.get_all(
                "Holiday",
                filters={"parent": ["in", holiday_lists], "holiday_date": getdate(day)},
                fields=["parent"],
            )
        }
    holiday_employees = {
        employee for employee, holiday_list in employee_lists.items()
        if holiday_list in holiday_list_names
    }
    return employee_lists, holiday_employees


def _holiday_payable_work_rows(work_rows, holiday_employees):
    """Operational Day Overrides never reprice native holiday pay."""
    return [row for row in work_rows if _get(row, "employee") not in holiday_employees]


def _daily_wage_override_candidates(rows, assignments):
    """Keep Daily Wage and unresolved workers; ignore only known Monthly staff."""
    return [
        row for row in rows
        if not assignments.get(_get(row, "employee"))
        or _get(assignments[_get(row, "employee")], "pay_basis") != "Monthly Salary"
    ]


def _ssa_map(employee_names, day):
    if not employee_names:
        return {}
    assignments = frappe.get_all(
        "Salary Structure Assignment",
        filters={"employee": ["in", employee_names], "docstatus": 1, "from_date": ["<=", day]},
        fields=["name", "employee", "company", "salary_structure", "base", "from_date"],
        order_by="employee asc, from_date desc, name desc",
    )
    grouped = defaultdict(list)
    for row in assignments:
        grouped[row.employee].append(row)
    structure_names = sorted({row.salary_structure for row in assignments if row.salary_structure})
    structures = {
        row.name: row.custom_tradex_pay_basis
        for row in frappe.get_all(
            "Salary Structure",
            filters={"name": ["in", structure_names]},
            fields=["name", "custom_tradex_pay_basis"],
        )
    } if structure_names else {}
    result = {}
    for employee, rows in grouped.items():
        latest_date = getdate(rows[0].from_date)
        latest = [row for row in rows if getdate(row.from_date) == latest_date]
        if len(latest) == 1:
            latest[0].pay_basis = structures.get(latest[0].salary_structure)
            result[employee] = latest[0]
        else:
            result[employee] = None
    return result


def build_operational_day_override_preview(doc):
    """Batch-load attendance and salary authority; this function writes nothing."""
    day = getdate(doc.operational_date)
    rows = frappe.get_all(
        "Attendance",
        filters={"company": doc.company, "attendance_date": day, "docstatus": 1},
        fields=["name", "employee", "attendance_date", "status", "working_hours",
                "half_day_status", "leave_type", "leave_application", "branch", "department"],
        order_by="employee asc",
    )
    scoped = [
        row for row in rows
        if (not doc.branch or row.branch == doc.branch)
        and (not doc.department or row.department == doc.department)
    ]
    work_rows = [row for row in scoped if row.status in {"Present", "Half Day", "Work From Home"}]
    employee_holiday_lists, holiday_employees = _native_holiday_context(
        sorted({row.employee for row in work_rows}), day
    )
    payable_work_rows = _holiday_payable_work_rows(work_rows, holiday_employees)
    candidate_rows = [
        row for row in payable_work_rows
        if row.status in {"Present", "Half Day"}
        and not row.leave_type and not row.leave_application
    ]
    candidate_names = sorted({row.employee for row in candidate_rows})
    assignments = _ssa_map(candidate_names, day)
    daily_candidates = _daily_wage_override_candidates(candidate_rows, assignments)
    employee_names = sorted({row.employee for row in daily_candidates})
    employees = {
        row.name: row for row in frappe.get_all(
            "Employee",
            filters={"name": ["in", employee_names]},
            fields=["name", "company"],
        )
    } if employee_names else {}
    findings = [
        {"code": "FLEX_ATTENDANCE_STATUS_CONFLICT", "employee": row.employee}
        for row in scoped
        if row.status in {"Absent", "On Leave"} and row.working_hours is not None and flt(row.working_hours) > 0
    ]
    for row in daily_candidates:
        assignment = assignments.get(row.employee)
        if not assignment or assignment.pay_basis != "Daily Wage" or flt(assignment.base) <= 0:
            findings.append({"code": "DAILY_WAGE_ASSIGNMENT_REQUIRED", "employee": row.employee})
        elif row.working_hours is None or flt(row.working_hours) <= 0:
            findings.append({"code": "FLEX_WORKING_HOURS_REQUIRED", "employee": row.employee})
    eligible = [
        row for row in daily_candidates
        if assignments.get(row.employee)
        and assignments[row.employee].pay_basis == "Daily Wage"
        and flt(assignments[row.employee].base) > 0
        and row.working_hours is not None and flt(row.working_hours) > 0
    ]
    policies = _active_policies(doc.company)
    half_fraction = flt(frappe.db.get_single_value("Payroll Settings", "daily_wages_fraction_for_half_day") or 0.5)
    affected = set()
    normal_units = override_units = impact = 0.0
    policy_names = set()

    for row in eligible:
        matches = _policy_for_row(policies, row)
        employee = employees.get(row.employee)
        if not employee or employee.company != doc.company:
            findings.append({"code": "EMPLOYEE_SCOPE_REVIEW_REQUIRED", "employee": row.employee})
            continue
        if len(matches) != 1:
            findings.append({
                "code": "FLEX_WORK_POLICY_REQUIRED" if not matches else "FLEX_WORK_POLICY_CONFLICT",
                "employee": row.employee,
            })
            continue
        policy = matches[0]
        policy_names.add(policy.name)
        assignment = assignments.get(row.employee)
        if not assignment or assignment.pay_basis != "Daily Wage" or flt(assignment.base) <= 0:
            if assignment and assignment.pay_basis != "Daily Wage":
                continue
            findings.append({"code": "DAILY_WAGE_ASSIGNMENT_REQUIRED", "employee": row.employee})
            continue
        try:
            units = calculate_flexible_work_units(row.working_hours, policy)
        except ValueError as exc:
            findings.append({"code": str(exc), "employee": row.employee})
            continue
        normal_units += units
        override_units += 1.0
        if units < 1.0:
            affected.add(row.employee)
            impact += (1.0 - units) * flt(assignment.base)

    payload = {
        "company": doc.company, "operational_date": str(day),
        "branch": doc.branch or "", "department": doc.department or "",
        "native_holiday_context": {
            "employee_lists": sorted(employee_holiday_lists.items()),
            "holiday_employees": sorted(holiday_employees),
        },
        "attendance": [
            {field: getattr(row, field, None) for field in (
                "name", "employee", "status", "working_hours", "half_day_status",
                "leave_type", "leave_application", "branch", "department",
            )}
            for row in scoped
        ],
        "policies": sorted(
            (policy.name, policy.branch, policy.department, str(policy.effective_from),
             str(policy.effective_to or ""), flt(policy.standard_paid_hours),
             flt(policy.full_day_minimum_hours))
            for policy in policies if policy.name in policy_names
        ),
        "salary_authority": sorted(
            (name, getattr(assignments.get(name), "name", None),
             getattr(assignments.get(name), "base", None),
             getattr(assignments.get(name), "salary_structure", None),
             getattr(assignments.get(name), "pay_basis", None))
            for name in employee_names
        ),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "status": "NEEDS_ATTENTION" if findings else "READY",
        "findings": findings,
        "present_count": len({row.employee for row in payable_work_rows}),
        "affected_count": len(affected),
        "normal_units": round(normal_units, 8),
        "override_units": round(override_units, 8),
        "amount_impact": flt(impact),
        "attendance_hash": digest,
    }


class TradexcelFlexibleWorkPolicy(Document):
    def validate(self):
        assert_company_access(self.company, require_explicit_scope=True)
        if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
            frappe.throw(_("Effective To must be on or after Effective From."))
        if flt(self.standard_paid_hours) <= 0 or not 0 < flt(self.full_day_minimum_hours) <= flt(self.standard_paid_hours):
            frappe.throw(_("Enter positive paid hours and a full-day threshold no greater than standard paid hours."))
        if self.branch and frappe.db.get_value("Branch", self.branch, "company") != self.company:
            frappe.throw(_("The policy Branch must belong to the selected Company."))
        if self.flexible_shift_enabled and not self.allowed_shift_types:
            frappe.throw(_("Select allowed native Shift Types when flexible scheduling is enabled."))
        shift_types = [row.shift_type for row in (self.allowed_shift_types or []) if row.shift_type]
        if len(shift_types) != len(set(shift_types)):
            frappe.throw(_("A native Shift Type may appear only once."))
        if len(shift_types) > 1:
            from hrms.hr.doctype.shift_assignment.shift_assignment import has_overlapping_timings
            for index, first in enumerate(shift_types):
                for second in shift_types[index + 1:]:
                    if has_overlapping_timings(first, second):
                        frappe.throw(_("Allowed Shift Types {0} and {1} overlap in native shift resolution.").format(first, second))
        if not (self.policy_notes or "").strip():
            frappe.throw(_("Record the approved operational policy and rationale."))
        self._validate_overlap()

    def _validate_overlap(self):
        others = frappe.get_all(
            self.doctype,
            filters={"company": self.company, "docstatus": 1, "name": ["!=", self.name]},
            fields=["name", "branch", "department", "effective_from", "effective_to"],
        )
        for other in others:
            scope_overlap = (
                (not self.branch or not other.branch or self.branch == other.branch)
                and (not self.department or not other.department or self.department == other.department)
            )
            if scope_overlap and (
                getdate(self.effective_from) <= getdate(other.effective_to or "9999-12-31")
                and getdate(other.effective_from) <= getdate(self.effective_to or "9999-12-31")
            ):
                frappe.throw(_("This effective policy overlaps approved policy {0}.").format(other.name))

    def before_submit(self):
        assert_company_access(self.company, require_explicit_scope=True)
        if frappe.session.user != "Administrator" and (
            APPROVER_ROLE not in frappe.get_roles() or self.owner == frappe.session.user
        ):
            frappe.throw(_("A different company-scoped Tradexcel Owner/Director must approve this policy."), frappe.PermissionError)
        periods = frappe.get_all(
            "Tradexcel Attendance Period",
            filters={"company": self.company, "status": "Finalized",
                     "from_date": ["<=", self.effective_to or "9999-12-31"],
                     "to_date": [">=", self.effective_from]},
            pluck="name", limit=1,
        )
        if periods:
            frappe.throw(_("Reopen finalized Attendance before activating a policy that would change its payroll inputs."))
        if self.flexible_shift_enabled and not frappe.db.get_single_value("HR Settings", "allow_multiple_shift_assignments"):
            frappe.throw(_("MULTIPLE_SHIFT_ASSIGNMENTS_SETTING_REQUIRED: enable the native setting only after explicit HR review."))
        self.approved_by = frappe.session.user
        self.approved_at = now_datetime()

    def on_submit(self):
        from tradex_hr.tradexcel_hr.flexible_work import clear_flexible_work_caches
        clear_flexible_work_caches()

    def before_update_after_submit(self):
        frappe.throw(_("Approved Flexible Work Policies are immutable; create a new effective version."))

    def on_cancel(self):
        from tradex_hr.tradexcel_hr.flexible_work import clear_flexible_work_caches
        clear_flexible_work_caches()

    def before_cancel(self):
        assert_company_access(self.company, require_explicit_scope=True)
        if frappe.session.user != "Administrator":
            if APPROVER_ROLE not in frappe.get_roles() or self.owner == frappe.session.user:
                frappe.throw(_("A different company-scoped Tradexcel Owner/Director must cancel this policy."), frappe.PermissionError)
        finalized = frappe.get_all(
            "Tradexcel Attendance Period",
            filters={"company": self.company, "status": "Finalized",
                     "from_date": ["<=", self.effective_to or "9999-12-31"],
                     "to_date": [">=", self.effective_from]},
            pluck="name", limit=1,
        )
        if finalized or _payroll_has_started(
            self.company, self.effective_from, self.effective_to or "9999-12-31"
        ):
            frappe.throw(_("This policy is historical payroll provenance and cannot be cancelled."))


class TradexcelOperationalDayOverride(Document):
    def validate(self):
        assert_company_access(self.company, require_explicit_scope=True)
        if self.branch and frappe.db.get_value("Branch", self.branch, "company") != self.company:
            frappe.throw(_("The override Branch must belong to the selected Company."))
        if not (self.reason or "").strip():
            frappe.throw(_("Record why management released this group early."))
        self.pay_treatment = "Full Day Pay for Present Employees"
        self._validate_overlap()
        preview = build_operational_day_override_preview(self)
        self.preview_status = preview["status"]
        self.preview_present_count = preview["present_count"]
        self.preview_affected_count = preview["affected_count"]
        self.preview_normal_units = preview["normal_units"]
        self.preview_override_units = preview["override_units"]
        self.preview_amount_impact = preview["amount_impact"]
        self.preview_hash = preview["attendance_hash"]

    def _validate_overlap(self):
        others = frappe.get_all(
            self.doctype,
            filters={"company": self.company, "operational_date": self.operational_date,
                     "docstatus": ["<", 2], "name": ["!=", self.name]},
            fields=["name", "branch", "department"],
        )
        for other in others:
            branch_overlap = not self.branch or not other.branch or self.branch == other.branch
            department_overlap = not self.department or not other.department or self.department == other.department
            if branch_overlap and department_overlap:
                frappe.throw(_("An operational-day override already exists for an overlapping scope: {0}.").format(other.name))

    def before_submit(self):
        assert_company_access(self.company, require_explicit_scope=True)
        if frappe.session.user != "Administrator" and (
            PAY_APPROVER_ROLE not in frappe.get_roles() or self.owner == frappe.session.user
        ):
            frappe.throw(_("A different company-scoped Tradexcel Payroll Approver must approve this pay decision."), frappe.PermissionError)
        persisted_hash = frappe.db.get_value(self.doctype, self.name, "preview_hash")
        current = build_operational_day_override_preview(self)
        if not persisted_hash or persisted_hash != current["attendance_hash"]:
            frappe.throw(_("Operational Day Override preview is stale; save and review it again."))
        if current["status"] != "READY" or current["affected_count"] < 1:
            frappe.throw(_("The preview must show at least one eligible Daily Wage employee and no unresolved findings."))
        finalized = frappe.get_all(
            "Tradexcel Attendance Period",
            filters={"company": self.company, "status": "Finalized",
                     "from_date": ["<=", self.operational_date], "to_date": [">=", self.operational_date]},
            pluck="name", limit=1,
        )
        if finalized:
            frappe.throw(_("Reopen the Attendance Period, approve the override, and finalize it again."))
        if _payroll_has_started(self.company, self.operational_date):
            frappe.throw(_("Payroll has started for this date; use the post-payroll adjustment review."))
        self.approved_by = frappe.session.user
        self.approved_at = now_datetime()

    def on_submit(self):
        from tradex_hr.tradexcel_hr.flexible_work import clear_flexible_work_caches
        clear_flexible_work_caches()

    def before_update_after_submit(self):
        frappe.throw(_("Approved operational-day pay decisions are immutable."))

    def on_cancel(self):
        from tradex_hr.tradexcel_hr.flexible_work import clear_flexible_work_caches
        clear_flexible_work_caches()

    def before_cancel(self):
        assert_company_access(self.company, require_explicit_scope=True)
        if frappe.session.user != "Administrator":
            if PAY_APPROVER_ROLE not in frappe.get_roles() or self.owner == frappe.session.user:
                frappe.throw(_("A different company-scoped Tradexcel Payroll Approver must cancel this override."), frappe.PermissionError)
        finalized = frappe.get_all(
            "Tradexcel Attendance Period",
            filters={"company": self.company, "status": "Finalized",
                     "from_date": ["<=", self.operational_date], "to_date": [">=", self.operational_date]},
            pluck="name", limit=1,
        )
        if finalized or _payroll_has_started(self.company, self.operational_date):
            frappe.throw(_("This operational-day pay decision has entered historical payroll and cannot be cancelled."))


def _payroll_has_started(company, start, end=None):
    start, end = getdate(start), getdate(end or start)
    date_range = {"start_date": ["<=", end], "end_date": [">=", start]}
    if frappe.get_all(
        "Salary Slip",
        filters={"company": company, "docstatus": ["<", 2], **date_range},
        pluck="name", limit=1,
    ):
        return True
    if frappe.get_all(
        "Payroll Entry",
        filters={"company": company, "docstatus": ["<", 2], **date_range,
                 "salary_slips_created": 1},
        pluck="name", limit=1,
    ):
        return True
    periods = frappe.get_all(
        "Tradexcel Attendance Period",
        filters={"company": company, "from_date": ["<=", end], "to_date": [">=", start]},
        pluck="name",
    )
    return bool(periods and frappe.db.exists(
        "Additional Salary",
        {"ref_doctype": "Tradexcel Attendance Period", "ref_docname": ["in", periods],
         "custom_tradex_payroll_input_key": ["like", "DAILY-WAGE:%"],
         "disabled": 0, "docstatus": ["<", 2]},
    ))


def validate_operational_day_overrides(company, start, end):
    rows = frappe.get_all(
        "Tradexcel Operational Day Override",
        filters={"company": company, "operational_date": ["between", [start, end]], "docstatus": 1},
        fields=["name", "company", "operational_date", "branch", "department", "preview_hash"],
    )
    findings = []
    for row in rows:
        preview = build_operational_day_override_preview(row)
        if preview["status"] != "READY" or preview["attendance_hash"] != row.preview_hash:
            findings.append({"code": "OPERATIONAL_DAY_OVERRIDE_PREVIEW_STALE", "record": row.name})
    return findings


def flexible_work_has_permission(doc, ptype=None, user=None, **_kwargs):
    user = user or frappe.session.user
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return True
    company = _get(doc, "company")
    if not company:
        return None
    if ptype in {"read", "select", "report", "export", "print"}:
        return bool(frappe.db.exists("User Permission", {"user": user, "allow": "Company", "for_value": company}))
    try:
        assert_company_access(company, require_explicit_scope=True)
    except frappe.PermissionError:
        return False
    return True


def _query_condition(doctype, user=None):
    user = user or frappe.session.user
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return ""
    companies = frappe.get_all("User Permission", filters={"user": user, "allow": "Company"}, pluck="for_value")
    if not companies:
        return "1=0"
    values = ", ".join(frappe.db.escape(company) for company in companies)
    return "company in ({0})".format(values)


def flexible_policy_query_conditions(user=None):
    return _query_condition("Tradexcel Flexible Work Policy", user)


def operational_override_query_conditions(user=None):
    return _query_condition("Tradexcel Operational Day Override", user)
