"""Approved, effective-dated exceptions for payroll and people policies.

One DocType, type-driven: Payroll exceptions feed the policy resolver and the
daily-wage payroll path. Holiday, Shift and Leave exceptions create the scoped
record on submit and remove it on cancel. Attendance and Tax are captured for
configuration and surfaced by the radar, but no automatic enforcement runs yet.
"""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, today

from tradex_hr.tradexcel_hr.attendance_exceptions import ATTENDANCE_SETTINGS
from tradex_hr.tradexcel_hr.effective_policy_rules import RuleConflict, preview_change, validate_rule
from tradex_hr.tradexcel_hr.tax_exceptions import TAX_ACTIONS


RULE_FIELDS = (
    "name", "rule_name", "reason", "company", "employee_category", "branch", "department", "designation",
    "employee", "min_tenure_months", "field_name", "value", "effective_from", "effective_to",
)
EXCEPTION_TYPES = ("Payroll", "Component", "Attendance", "Leave", "Holiday", "Shift", "Tax")


def _rule(doc):
    return {field: doc.get(field) for field in RULE_FIELDS}


def _require(condition, message):
    if not condition:
        frappe.throw(_(message))


def _base_value(policies, employee, day, field):
    category = "Worker" if employee.get("employment_type") == "Worker" else "Staff"
    matching = [
        policy for policy in policies
        if policy.company == employee["company"]
        and policy.employee_category == category
        and getdate(policy.effective_from) <= day
        and (not policy.branch or policy.branch == employee.get("branch"))
        and (not policy.department or policy.department == employee.get("department"))
    ]
    if not matching:
        return None
    matching.sort(key=lambda policy: (
        bool(policy.department), bool(policy.branch), getdate(policy.effective_from), policy.modified
    ), reverse=True)
    return matching[0].get(field)


def calculate_preview(doc):
    start = getdate(doc.effective_from)
    end = getdate(doc.effective_to) if doc.effective_to else max(
        getdate(today()) + timedelta(days=30), start + timedelta(days=30)
    )
    if end < start:
        end = start
    employees = frappe.get_all(
        "Employee", filters={"company": doc.company},
        fields=["name", "company", "branch", "department", "designation",
                "employment_type", "date_of_joining", "modified"],
    )
    active_rules = frappe.get_all(
        "Tradexcel Policy Exception", filters={"company": doc.company, "docstatus": 1,
                                               "exception_type": "Payroll"},
        fields=[*RULE_FIELDS, "modified"],
    )
    policies = frappe.get_all(
        "Tradexcel Payroll Policy", filters={"company": doc.company, "enabled": 1}, fields="*"
    )
    slips = frappe.get_all(
        "Salary Slip", filters={"company": doc.company, "docstatus": ["<", 2],
                                "start_date": ["<=", end], "end_date": [">=", start]},
        fields=["name", "employee", "start_date", "end_date", "docstatus", "modified"],
    )
    try:
        result = preview_change(
            employees, active_rules, _rule(doc), start, end,
            [slip for slip in slips if slip.docstatus == 1],
            draft_slips=[slip for slip in slips if slip.docstatus == 0],
            base_value=lambda employee, day, field: _base_value(policies, employee, day, field),
        )
    except RuleConflict as exc:
        frappe.throw(_("Conflicting {0} rules need review before this change can be previewed: {1}").format(
            exc.field, ", ".join(exc.names)))
    except ValueError as exc:
        frappe.throw(_(str(exc)))
    result["preview_from"] = str(start)
    result["preview_through"] = str(end)
    result["ongoing_beyond_preview"] = not bool(doc.effective_to)
    employee_by_name = {employee.name: employee for employee in employees}
    result["missing_base_employees"] = sorted({
        row["employee"] for row in result["changes"]
        if _base_value(policies, employee_by_name[row["employee"]], getdate(row["from_date"]),
                       doc.field_name) is None
    })
    affected_slips = [slip for slip in slips if slip.name in result["submitted_slips"]]
    result["suggested_unpaid_start"] = (
        str(max(getdate(slip.end_date) for slip in affected_slips) + timedelta(days=1))
        if affected_slips else None
    )
    payload = {
        "candidate": _rule(doc), "employees": employees, "active_rules": active_rules,
        "base_policies": policies, "submitted_slips": slips, "result": result,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return result, digest


def calculate_scope_preview(doc):
    from tradex_hr.tradexcel_hr.attendance_exceptions import build_attendance_rule
    from tradex_hr.tradexcel_hr.component_exceptions import (
        branch_scope_map, build_rule, department_scope_map, scope_match,
    )

    if doc.exception_type in ("Leave", "Holiday", "Shift", "Tax"):
        employee_name = frappe.db.get_value("Employee", doc.employee, "employee_name") or doc.employee
        if doc.exception_type == "Leave":
            action_text = f"{float(doc.extra_days or 0):g} extra {doc.leave_type} day(s)"
        elif doc.exception_type == "Holiday":
            action_text = f"assign Holiday List {doc.holiday_list}"
        elif doc.exception_type == "Shift":
            action_text = f"assign Shift {doc.shift_type}"
        else:
            action_text = doc.tax_action or ""
        summary = _("{0}: {1} for {2} from {3} to {4}.").format(
            doc.rule_name, action_text, employee_name,
            doc.effective_from, doc.effective_to or _("ongoing"))
        payload = {
            "type": doc.exception_type, "employee": doc.employee, "action": action_text,
            "from": str(doc.effective_from), "to": str(doc.effective_to or ""),
            "scope": [doc.branch, doc.department, doc.designation],
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        return summary, digest, [employee_name]

    if doc.exception_type == "Attendance":
        action_text = f"{doc.attendance_setting or ''} {float(doc.attendance_value or 0):g}".strip()
        rule = build_attendance_rule(doc, branch_scope_map(), department_scope_map(),
                                     include_children=bool(doc.get("include_child_scope")))
    else:
        action_text = f"{doc.component_action or ''} on {doc.salary_component or ''}"
        rule = build_rule(doc, branch_scope_map(), department_scope_map(),
                          include_children=bool(doc.get("include_child_scope")))
    employees = frappe.get_all(
        "Employee",
        filters={"company": doc.company, "status": "Active"},
        fields=["name", "employee_name", "company", "branch", "department", "designation"],
    )
    matching = [row for row in employees if scope_match(row, rule)]
    names = sorted(row.employee_name or row.name for row in matching)
    summary = _("{0}: {1} for {2} active employees. First: {3}").format(
        doc.rule_name, _(action_text), len(matching), ", ".join(names[:8]) or _("none"))
    scope_parts = []
    if rule.get("branch_scope"):
        scope_parts.append("Branches: " + ", ".join(rule["branch_scope"]))
    if rule.get("department_scope"):
        scope_parts.append("Departments: " + ", ".join(rule["department_scope"]))
    if scope_parts:
        summary += " " + _("Scope: {0}.").format("; ".join(scope_parts))
    digest = hashlib.sha256(
        json.dumps({"rule": rule, "employees": names}, sort_keys=True, default=str).encode()
    ).hexdigest()
    return summary, digest, names


class TradexcelPolicyException(Document):
    def validate(self):
        _require(self.exception_type in EXCEPTION_TYPES, "Select a valid exception type")
        if not self.effective_from:
            self.effective_from = str(getdate(today()) + timedelta(days=1))
        if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
            frappe.throw(_("Effective To must not precede Effective From"))
        if self.exception_type == "Payroll":
            self._validate_payroll()
            self.enforcement_note = "Enforced: merged into payroll policy resolution per effective date."
        elif self.exception_type == "Component":
            self._validate_component()
            self.enforcement_note = "Enforced: filters or overrides this component on salary slips per effective date."
        elif self.exception_type == "Attendance":
            self._validate_attendance()
            self.enforcement_note = "Enforced: applies ignore/grace settings to attendance records in scope."
        else:
            self._validate_employee_scoped()
            if self.exception_type == "Tax":
                self.enforcement_note = "Enforced: removes income-tax deduction components on this employee's salary slips."
            else:
                self.enforcement_note = "Enforced: creates the scoped record on submit and removes it on cancel."

    def _employee_target(self):
        target = frappe.db.get_value(
            "Employee", self.employee,
            ["name", "company", "branch", "department", "designation", "employment_type"],
            as_dict=True,
        )
        if not target or target.company != self.company:
            frappe.throw(_("Selected employee must belong to the selected company"))
        return target

    def _validate_payroll(self):
        _require(self.employee_category in {"Worker", "Staff"}, "Select the employee category")
        if not self.field_name or self.value is None:
            frappe.throw(_("Select the setting and enter the new value"))
        try:
            validate_rule({**_rule(self), "reason": self.reason})
        except ValueError as exc:
            frappe.throw(_(str(exc)))
        if not self.employee:
            return
        target = self._employee_target()
        derived = "Worker" if target.employment_type == "Worker" else "Staff"
        if derived != self.employee_category:
            frappe.throw(_("Selected employee is category {0}; choose the matching category").format(derived))
        for field in ("branch", "department", "designation"):
            if self.get(field) and self.get(field) != target.get(field):
                frappe.throw(_("Selected employee does not match the chosen {0}").format(field))

    def _validate_component(self):
        _require(self.salary_component, "Select the Salary Component")
        _require(self.component_action in {"Exclude", "Include", "Override Amount"},
                 "Select the component action")
        if self.component_action == "Override Amount":
            _require(self.component_amount is not None and float(self.component_amount) >= 0,
                     "Enter a non-negative override amount")
        if self.employee:
            self._employee_target()

    def _validate_attendance(self):
        _require(self.attendance_setting in ATTENDANCE_SETTINGS, "Select the attendance setting")
        if self.attendance_setting and "Minutes" in self.attendance_setting:
            _require(self.attendance_value is not None and float(self.attendance_value) >= 0,
                     "Enter a non-negative number of minutes")
        if self.employee:
            self._employee_target()

    def _validate_employee_scoped(self):
        _require(self.employee, _("This exception type applies to one specific employee"))
        target = self._employee_target()
        if self.branch and self.branch != target.branch:
            frappe.throw(_("Selected employee does not belong to the chosen Branch"))
        if self.exception_type == "Holiday":
            _require(self.holiday_list, "Select the Holiday List to assign")
            _require(self.employee, "Select the Employee")
        elif self.exception_type == "Shift":
            _require(self.shift_type, "Select the Shift Type to assign")
        elif self.exception_type == "Leave":
            _require(self.leave_type, "Select the Leave Type")
            _require(self.extra_days and float(self.extra_days) > 0, "Extra days must be greater than zero")
        elif self.exception_type == "Tax":
            _require(self.tax_action in TAX_ACTIONS, "Select the tax action")

    def before_submit(self):
        if frappe.session.user != "Administrator":
            if "Tradexcel Payroll Approver" not in frappe.get_roles():
                frappe.throw(_("Only a payroll approver may activate a policy exception."))
            if self.owner == frappe.session.user:
                frappe.throw(_("The person who prepared this rule cannot approve it."))
        if self.exception_type != "Payroll":
            _summary, digest, _names = calculate_scope_preview(self)
            if not self.preview_signature or self.preview_signature != digest:
                frappe.throw(_("Impact preview is missing or stale. Save and run Preview Impact again."))
            return
        if self.exception_type != "Payroll":
            return
        result, digest = calculate_preview(self)
        if not self.preview_signature or self.preview_signature != digest:
            frappe.throw(_("Impact preview is missing or stale. Save and run Preview Impact again."))
        if result["submitted_slips"]:
            frappe.throw(_("This rule affects submitted salary slips. Reconciliation is required before activation; no slips were changed. First date beyond affected slips: {0}.").format(result["suggested_unpaid_start"]))
        if result["draft_slips"]:
            frappe.throw(_("This rule affects {0} existing draft salary slips. Reprice and review those drafts before activating the rule; no slips were changed.").format(len(result["draft_slips"])))
        if result["missing_base_employees"]:
            frappe.throw(_("Some affected workers have no base payroll policy. Fix coverage before activation."))

    def before_cancel(self):
        if self.exception_type == "Payroll":
            frappe.throw(_("Submitted payroll rules are audit history. Create a new, dated superseding rule instead."))

    def on_submit(self):
        if self.exception_type == "Holiday":
            self._apply_holiday()
        elif self.exception_type == "Shift":
            self._apply_shift()
        elif self.exception_type == "Leave":
            self._apply_leave()

    def on_cancel(self):
        self._remove_applied()

    def _link(self, reference):
        self.applied_reference = reference
        frappe.db.set_value(self.doctype, self.name, "applied_reference", reference, update_modified=False)

    def _apply_holiday(self):
        previous = frappe.db.get_value("Employee", self.employee, "holiday_list") or ""
        frappe.db.set_value("Employee", self.employee, "holiday_list", self.holiday_list)
        self._link(f"Employee:{self.employee}|{previous}")

    def _apply_shift(self):
        overlap = frappe.db.sql(
            """
            SELECT name FROM `tabShift Assignment`
            WHERE employee = %(employee)s AND docstatus = 1
              AND start_date <= COALESCE(%(end)s, '2099-12-31')
              AND COALESCE(end_date, '2099-12-31') >= %(start)s
            LIMIT 1
            """,
            {"employee": self.employee, "start": self.effective_from, "end": self.effective_to},
            as_dict=True,
        )
        if overlap:
            frappe.throw(_(
                "Employee already has active Shift Assignment {0} covering these dates. "
                "Adjust or cancel it first, or enable Allow Multiple Shift Assignments in HR Settings."
            ).format(overlap[0].name))
        assignment = frappe.get_doc({
            "doctype": "Shift Assignment",
            "employee": self.employee,
            "company": self.company,
            "shift_type": self.shift_type,
            "start_date": self.effective_from,
            "end_date": self.effective_to or None,
            "status": "Active",
        })
        assignment.insert(ignore_permissions=True)
        assignment.submit()
        self._link(assignment.name)

    def _apply_leave(self):
        meta = frappe.get_meta("Leave Allocation")
        series = (meta.get_field("naming_series").options or "").splitlines() or ["HR-LAL-.YYYY.-"]
        payload = {
            "doctype": "Leave Allocation",
            "naming_series": series[0].strip(),
            "employee": self.employee,
            "company": self.company,
            "leave_type": self.leave_type,
            "from_date": self.effective_from,
            "to_date": self.effective_to or self.effective_from,
            "total_leaves_allocated": self.extra_days,
        }
        for fieldname in ("new_leaves_allocated", "unused_leaves"):
            if meta.has_field(fieldname):
                payload[fieldname] = self.extra_days
        allocation = frappe.get_doc(payload)
        allocation.insert(ignore_permissions=True, ignore_mandatory=True)
        allocation.submit()
        self._link(allocation.name)

    def _remove_applied(self):
        reference = self.applied_reference
        if not reference:
            return
        if reference.startswith("Employee:"):
            employee, _, previous = reference.split(":", 1)[1].partition("|")
            frappe.db.set_value("Employee", employee, "holiday_list", previous or None)
            return
        if reference.startswith("existing:"):
            return
        for doctype in ("Shift Assignment", "Leave Allocation"):
            if not frappe.db.exists(doctype, reference):
                continue
            doc = frappe.get_doc(doctype, reference)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc(doctype, reference, ignore_permissions=True, force=True)
            return


@frappe.whitelist(methods=["POST"])
def preview_impact(name: str):
    doc = frappe.get_doc("Tradexcel Policy Exception", name)
    doc.check_permission("write")
    if doc.docstatus != 0:
        frappe.throw(_("Only draft rules can be previewed."))
    if doc.exception_type != "Payroll":
        doc.validate()
        summary, digest, names = calculate_scope_preview(doc)
        frappe.db.set_value(doc.doctype, doc.name, {
            "preview_signature": digest,
            "preview_summary": summary,
            "previewed_at": now_datetime(),
        })
        return {"summary": summary, "affected_employees": len(names),
                "submitted_slips": [], "draft_slips": []}
    if doc.exception_type != "Payroll":
        frappe.throw(_("Impact preview applies to Payroll and Component exceptions."))
    doc.validate()
    result, digest = calculate_preview(doc)
    summary = _("{0} employees, {1} employee-days affected; {2} submitted slips, {3} draft slips; {4} to {5}.").format(
        result["affected_employees"], result["affected_days"],
        len(result["submitted_slips"]), len(result["draft_slips"]),
        result["preview_from"], result["preview_through"],
    )
    if result["ongoing_beyond_preview"]:
        summary += " " + _("Ongoing rule: future dates beyond this preview are not shown.")
    if result["missing_base_employees"]:
        summary += " " + _("Missing base policy for {0} workers.").format(len(result["missing_base_employees"]))
    if result["suggested_unpaid_start"]:
        summary += " " + _("First date beyond affected paid periods: {0}.").format(result["suggested_unpaid_start"])
    frappe.db.set_value(doc.doctype, doc.name, {
        "preview_signature": digest,
        "preview_summary": summary,
        "previewed_at": now_datetime(),
    })
    return {"summary": summary, **result}
