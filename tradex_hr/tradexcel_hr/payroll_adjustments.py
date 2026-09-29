"""Authorization and lifecycle guards around native Payroll Correction and Arrear.

HRMS remains responsible for all component, tax, and benefit calculations. This
module validates provenance, approval, company scope, target period, and safe
cancellation; it creates only native Additional Salary / Employee Benefit Ledger
records from values already produced by the native controllers.
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate

MAKERS = {"Tradexcel Payroll Manager", "Tradexcel HR Manager"}
APPROVERS = {"Tradexcel Payroll Approver"}
DIRECTORS = {"Tradexcel Owner/Director"}
PRIVILEGED = {"System Manager"}
PENDING = "Tradexcel Adjustment Pending Approval"
APPROVED = "Tradexcel Adjustment Approved"
DRAFT = "Tradexcel Adjustment Draft"
REJECTED = "Tradexcel Adjustment Rejected"
CANCELLED = "Tradexcel Adjustment Cancelled"
ADJUSTMENT_TYPES = {"Payroll Correction", "Arrear"}


def _roles(user=None) -> set[str]:
    user = user or frappe.session.user
    return set(frappe.get_roles(user))


def _is_privileged(user=None) -> bool:
    user = user or frappe.session.user
    return user == "Administrator" or bool(_roles(user) & PRIVILEGED)


def _authorize_company(company: str, *, user=None) -> None:
    user = user or frappe.session.user
    if not company or not frappe.db.exists("Company", company):
        frappe.throw(_("Choose a valid Company before preparing a payroll adjustment."))
    if _is_privileged(user):
        return
    if not (_roles(user) & (MAKERS | APPROVERS | DIRECTORS)):
        frappe.throw(_("You are not authorized to access payroll adjustments."), frappe.PermissionError)
    if not frappe.db.exists(
        "User Permission", {"user": user, "allow": "Company", "for_value": company}
    ):
        frappe.throw(
            _("An explicit Company User Permission is required for {0}.").format(company),
            frappe.PermissionError,
        )



def _independent_approval_transition(doc, user, roles, state, status) -> bool:
    """Permit Frappe's submit/write checks only during pending-to-approved transition."""
    return bool(
        roles & APPROVERS
        and status == 1
        and state == APPROVED
        and doc.get("name")
        and doc.get("owner") != user
        and frappe.db.get_value(doc.doctype, doc.name, "workflow_state") == PENDING
    )


def adjustment_has_permission(doc, ptype, user=None, debug=False):
    """Deny native broad HRMS permissions unless the user has a Tradexcel role."""
    user = user or frappe.session.user
    if _is_privileged(user):
        return True

    roles = _roles(user)
    maker = bool(roles & MAKERS)
    approver = bool(roles & APPROVERS)
    director = bool(roles & DIRECTORS)
    company = doc.get("company") if doc else None
    if not (maker or approver or director):
        return False
    if ptype == "create" and not company:
        # The new form has no company yet; exact User Permission is enforced
        # before insertion by _authorize_company().
        return maker
    if not company:
        return False
    if not frappe.db.exists(
        "User Permission", {"user": user, "allow": "Company", "for_value": company}
    ):
        return False

    state = doc.get("workflow_state") if doc else None
    status = int(doc.get("docstatus") or 0) if doc else 0
    if ptype in {"read", "select", "report", "print", "export"}:
        return True
    if ptype == "create":
        return maker
    if ptype == "write":
        if status == 0:
            return maker or (approver and state in {PENDING, REJECTED})
        if status == 1 and approver and state == APPROVED and doc.name:
            # Frappe sets docstatus=1 before checking write permission during
            # apply_workflow()'s Draft -> Submitted transition. Permit only an
            # independent approver moving the persisted Pending record to
            # Approved; normal edits to submitted adjustments remain denied.
            return (
                doc.owner != user
                and frappe.db.get_value(doc.doctype, doc.name, "workflow_state") == PENDING
            )
        return False
    if ptype == "submit":
        return (
            (approver and status == 0 and state in {PENDING, APPROVED})
            or _independent_approval_transition(doc, user, roles, state, status)
        )
    if ptype == "cancel":
        return director and status == 1 and state in {APPROVED, CANCELLED}
    if ptype == "delete":
        return False
    return None


def _authorize_document(doc, *, action: str) -> None:
    _authorize_company(doc.get("company"))
    roles = _roles()
    if _is_privileged():
        return
    if action == "make" and roles & MAKERS:
        return
    if action == "validate" and roles & APPROVERS:
        return
    if action == "approve" and roles & APPROVERS:
        return
    if action == "cancel" and roles & DIRECTORS:
        return
    frappe.throw(_("You do not have the Tradexcel role required for this adjustment action."), frappe.PermissionError)


def initialize_adjustment_state(doc, method=None) -> None:
    if doc.is_new() and not doc.get("workflow_state"):
        doc.workflow_state = DRAFT


def _employee_company(employee: str) -> str | None:
    return frappe.db.get_value("Employee", employee, "company")


def _target_payroll_has_started(employee: str, company: str, payroll_date) -> bool:
    """Return whether payroll processing has started for this employee/date."""
    if not employee or not company or not payroll_date:
        return False

    if frappe.get_all(
        "Salary Slip",
        filters={
            "employee": employee,
            "company": company,
            "docstatus": ["<", 2],
            "start_date": ["<=", payroll_date],
            "end_date": [">=", payroll_date],
        },
        pluck="name",
        limit=1,
    ):
        return True

    payroll_entries = frappe.get_all(
        "Payroll Entry",
        filters={
            "company": company,
            "docstatus": 1,
            "start_date": ["<=", payroll_date],
            "end_date": [">=", payroll_date],
        },
        fields=[
            "name",
            "status",
            "salary_slips_created",
            "custom_tradex_run_key",
        ],
    )
    active_managed_entries = [
        entry
        for entry in payroll_entries
        if entry.custom_tradex_run_key
        and (entry.status == "Queued" or flt(entry.salary_slips_created))
    ]
    if not active_managed_entries:
        return False

    return bool(
        frappe.get_all(
            "Payroll Employee Detail",
            filters={
                "parent": ["in", [entry.name for entry in active_managed_entries]],
                "parenttype": "Payroll Entry",
                "parentfield": "employees",
                "employee": employee,
            },
            pluck="parent",
            limit=1,
        )
    )


def _reject_target_payroll_if_started(doc) -> None:
    target_date = doc.get("payroll_date")
    if _target_payroll_has_started(doc.get("employee"), doc.get("company"), target_date):
        frappe.throw(
            _(
                "TARGET_PAYROLL_ALREADY_STARTED: A non-cancelled Salary Slip or active "
                "managed Payroll Entry already covers {0}. Choose a later payroll date."
            ).format(frappe.bold(target_date))
        )


def _validate_managed_source_slip(slip) -> None:
    payroll_entry = slip.get("payroll_entry")
    if not payroll_entry:
        return  # Imported/unmanaged historical payroll remains explicitly reviewable.
    run_key = frappe.db.get_value("Payroll Entry", payroll_entry, "custom_tradex_run_key")
    if not run_key:
        return
    from tradex_hr.tradexcel_hr.payroll_finalization import inspect_payroll_accrual_reconciliation

    result = inspect_payroll_accrual_reconciliation(payroll_entry)
    if result.get("status") != "READY":
        frappe.throw(
            _("SOURCE_PAYROLL_NOT_FINALIZED: Source payroll has not completed native accrual reconciliation ({0}).").format(
                result.get("status")
            )
        )


def _validation_action(doc) -> str:
    """Allow approvers to run the native validate hook during workflow decisions."""
    meta = getattr(doc, "meta", None)
    if not doc.get("name") or not meta or not meta.has_field("workflow_state"):
        return "make"
    old_state = frappe.db.get_value(doc.doctype, doc.name, "workflow_state")
    if old_state == PENDING and doc.get("workflow_state") in {APPROVED, REJECTED}:
        return "validate"
    return "make"


def validate_payroll_correction(doc, method=None, *, action=None) -> None:
    _authorize_document(doc, action=action or _validation_action(doc))
    employee_company = _employee_company(doc.employee)
    if employee_company != doc.company:
        frappe.throw(_("Payroll Correction employee and company do not match."))

    period = frappe.get_doc("Payroll Period", doc.payroll_period)
    if period.company != doc.company:
        frappe.throw(_("Payroll Correction company must match its Payroll Period."))

    slip = frappe.get_doc("Salary Slip", doc.salary_slip_reference)
    if slip.docstatus != 1:
        frappe.throw(_("A Payroll Correction must reference a submitted historical Salary Slip."))
    if slip.employee != doc.employee or slip.company != doc.company:
        frappe.throw(_("The selected Salary Slip must belong to the same employee and company."))
    if slip.current_payroll_period != doc.payroll_period:
        frappe.throw(_("The selected Salary Slip must belong to the selected Payroll Period."))
    if (
        getdate(slip.start_date) < getdate(period.start_date)
        or getdate(slip.end_date) > getdate(period.end_date)
    ):
        frappe.throw(_("The selected Salary Slip dates must be inside the selected Payroll Period."))

    eligible_lwp = max(flt(slip.total_working_days) - flt(slip.payment_days), 0)
    if flt(doc.days_to_reverse) > eligible_lwp:
        frappe.throw(_("Days to reverse cannot exceed the source Salary Slip's eligible LWP days."))
    if getdate(doc.payroll_date) <= getdate(slip.end_date):
        frappe.throw(_("Payroll Correction must target a payroll date after the source Salary Slip period."))

    _validate_managed_source_slip(slip)
    _reject_target_payroll_if_started(doc)


def validate_arrear(doc, method=None, *, action=None) -> None:
    _authorize_document(doc, action=action or _validation_action(doc))
    if _employee_company(doc.employee) != doc.company:
        frappe.throw(_("Arrear employee and company do not match."))

    period = frappe.get_doc("Payroll Period", doc.payroll_period)
    if period.company != doc.company:
        frappe.throw(_("Arrear company must match its Payroll Period."))
    structure_company = frappe.db.get_value("Salary Structure", doc.salary_structure, "company")
    if structure_company and structure_company != doc.company:
        frappe.throw(_("Arrear Salary Structure must belong to the same company."))

    if getdate(doc.payroll_date) <= getdate(period.end_date):
        frappe.throw(_("Arrear must target a payroll date after the selected historical Payroll Period."))
    _reject_target_payroll_if_started(doc)


def _business_fields_changed(doc, old_doc) -> bool:
    ignored = {"workflow_state", "modified", "modified_by", "creation", "owner", "docstatus"}
    return any(
        doc.get(field.fieldname) != old_doc.get(field.fieldname)
        for field in doc.meta.fields
        if field.fieldname not in ignored
    )


def validate_adjustment_before_save(doc, method=None) -> None:
    old = doc.get_doc_before_save()
    if not old or old.get("workflow_state") not in {PENDING, REJECTED}:
        return
    if doc.get("workflow_state") not in {PENDING, APPROVED, REJECTED, DRAFT}:
        frappe.throw(_("Invalid payroll adjustment workflow transition."))
    if _business_fields_changed(doc, old):
        frappe.throw(_("A pending or rejected payroll adjustment cannot be edited. Return it to Draft through the workflow first."))


def validate_adjustment_before_submit(doc, method=None) -> None:
    if _is_privileged():
        return
    old_state = frappe.db.get_value(doc.doctype, doc.name, "workflow_state")
    if (
        old_state != PENDING
        or doc.get("workflow_state") != APPROVED
        or frappe.session.user == doc.owner
        or not (_roles() & APPROVERS)
    ):
        frappe.throw(_("Only an independent Payroll Approver can approve a pending adjustment."))
    _authorize_document(doc, action="approve")
    if doc.doctype == "Payroll Correction":
        validate_payroll_correction(doc, action="validate")
    else:
        validate_arrear(doc, action="validate")


def _adjustment_additional_salaries(doc):
    return frappe.get_all(
        "Additional Salary",
        filters={
            "ref_doctype": doc.doctype,
            "ref_docname": doc.name,
            "docstatus": 1,
        },
        fields=["name"],
    )


def _additional_salary_consumers(additional_salary_names: list[str]) -> list[str]:
    if not additional_salary_names:
        return []
    return frappe.db.sql(
        """
        SELECT DISTINCT ss.name
        FROM `tabSalary Slip` ss
        INNER JOIN `tabSalary Detail` sd ON sd.parent = ss.name
        WHERE sd.parenttype = 'Salary Slip'
          AND sd.additional_salary IN %(names)s
          AND ss.docstatus < 2
        """,
        {"names": tuple(additional_salary_names)},
        pluck=True,
    )


def _benefit_ledger_consumers(doc) -> list[str]:
    entries = frappe.get_all(
        "Employee Benefit Ledger",
        filters={"reference_doctype": doc.doctype, "reference_document": doc.name},
        fields=["employee", "payroll_period", "salary_component", "creation"],
    )
    consumers = []
    for entry in entries:
        if not entry.payroll_period or not entry.salary_component:
            continue
        slip_names = frappe.get_all(
            "Employee Benefit Ledger",
            filters={
                "employee": entry.employee,
                "payroll_period": entry.payroll_period,
                "salary_component": entry.salary_component,
                "salary_slip": ["is", "set"],
                "reference_doctype": ["!=", doc.doctype],
                "reference_document": ["!=", doc.name],
                "creation": [">=", entry.creation],
            },
            pluck="salary_slip",
        )
        if slip_names:
            consumers.extend(frappe.get_all(
                "Salary Slip",
                filters={"name": ["in", slip_names], "docstatus": 1},
                pluck="name",
            ))
    return sorted(set(consumers))


def validate_adjustment_before_cancel(doc, method=None) -> None:
    if doc.get("workflow_state") != CANCELLED:
        frappe.throw(_("Use the adjustment workflow to reject or cancel this record."))
    _authorize_document(doc, action="cancel")
    salaries = _adjustment_additional_salaries(doc)
    names = [row.name for row in salaries]
    consumers = _additional_salary_consumers(names)
    consumers.extend(_benefit_ledger_consumers(doc))
    if consumers:
        frappe.throw(
            _("ADJUSTMENT_ALREADY_CONSUMED: Additional Salary has been used by Salary Slip(s) {0}. Keep history and create a future adjustment.").format(
                ", ".join(consumers[:5])
            )
        )

    frappe.flags.tradex_adjustment_parent_cancel = True
    try:
        for row in salaries:
            adjustment = frappe.get_doc("Additional Salary", row.name)
            adjustment.flags.ignore_permissions = True
            adjustment.cancel()
    finally:
        frappe.flags.tradex_adjustment_parent_cancel = False


def validate_additional_salary_before_cancel(doc, method=None) -> None:
    if (
        doc.get("ref_doctype") in ADJUSTMENT_TYPES
        and not getattr(frappe.flags, "tradex_adjustment_parent_cancel", False)
        and frappe.db.get_value(doc.ref_doctype, doc.ref_docname, "docstatus") == 1
    ):
        frappe.throw(_("Cancel an unconsumed Payroll Correction or Arrear through its approved workflow."))


def _create_submitted_additional_salary(values: dict):
    """Create native money only after the approved adjustment is submitted."""
    doc = frappe.get_doc({"doctype": "Additional Salary", **values})
    doc.insert(ignore_permissions=True)
    doc.flags.ignore_permissions = True
    doc.submit()
    return doc

def _insert_employee_benefit_ledger(values: dict):
    """Insert the non-submittable native benefit ledger from an approved adjustment."""
    doc = frappe.get_doc({"doctype": "Employee Benefit Ledger", **values})
    doc.insert(ignore_permissions=True)
    return doc


class PayrollCorrectionMixin:
    """Retain HRMS values while inserting linked native money under approval control."""

    def create_additional_salary(self):
        for component in (self.earning_arrears or []) + (self.deduction_arrears or []):
            _create_submitted_additional_salary({
                "employee": self.employee,
                "company": self.company,
                "payroll_date": self.payroll_date,
                "salary_component": component.salary_component,
                "currency": self.currency,
                "amount": component.amount,
                "ref_doctype": "Payroll Correction",
                "ref_docname": self.name,
                "overwrite_salary_structure_amount": 0,
            })

    def create_benefit_ledger_entry(self):
        for component in self.accrual_arrears or []:
            if not component.salary_component or not component.amount:
                continue
            flexible = frappe.db.get_value(
                "Salary Component", component.salary_component, "is_flexible_benefit"
            )
            _insert_employee_benefit_ledger({
                "employee": self.employee,
                "employee_name": self.employee_name,
                "company": self.company,
                "payroll_period": self.payroll_period,
                "salary_component": component.salary_component,
                "transaction_type": "Accrual",
                "amount": component.amount,
                "reference_doctype": "Payroll Correction",
                "reference_document": self.name,
                "remarks": "Accrual via Payroll Correction",
                "salary_slip": self.salary_slip_reference,
                "flexible_benefit": flexible,
            })


class TradexcelArrearMixin:
    """Bound only the source Salary Slips; native Arrear still calculates amounts."""

    def get_existing_salary_slips(self):
        period = self.payroll_period_details
        if period.company != self.company:
            frappe.throw(_("Arrear company must match its Payroll Period."))
        slips = frappe.get_all(
            "Salary Slip",
            filters={
                "employee": self.employee,
                "company": self.company,
                "docstatus": 1,
                "start_date": [">=", max(getdate(self.arrear_start_date), getdate(period.start_date))],
                "end_date": ["<=", period.end_date],
            },
            fields=["name", "posting_date", "start_date", "end_date"],
            order_by="start_date",
        )
        if not slips:
            frappe.throw(
                _("No submitted Salary Slips for {0} fall within Payroll Period {1} from {2}.").format(
                    self.employee, self.payroll_period, self.arrear_start_date
                )
            )
        return slips

    def compute_component_differences(self, existing_components: dict, new_components: dict):
        for section in ("earnings", "deductions", "accruals"):
            old_amounts = (existing_components or {}).get(section, {})
            new_amounts = (new_components or {}).get(section, {})
            reduced = [
                component
                for component in old_amounts.keys() | new_amounts.keys()
                if flt(new_amounts.get(component)) < flt(old_amounts.get(component))
            ]
            if reduced:
                frappe.throw(
                    _("RETRO_OVERPAYMENT_DECISION_REQUIRED: Retroactive component reductions need an HR/Finance decision; no automatic recovery or refund was created ({0}).").format(
                        ", ".join(sorted(reduced))
                    )
                )

        try:
            return super().compute_component_differences(existing_components, new_components)
        except frappe.ValidationError as exc:
            if "no arrear differences" in str(exc).lower():
                frappe.throw(
                    _("There is no positive native arrear to create. If the retroactive change reduces pay, HR and Finance must decide the recovery method; no automatic deduction was created.")
                )
            raise

    def create_additional_salary(self):
        for component in (self.earning_arrears or []) + (self.deduction_arrears or []):
            if not component.salary_component or not component.amount:
                continue
            _create_submitted_additional_salary({
                "employee": self.employee,
                "company": self.company,
                "payroll_date": self.payroll_date,
                "salary_component": component.salary_component,
                "currency": self.currency,
                "amount": component.amount,
                "ref_doctype": "Arrear",
                "ref_docname": self.name,
                "overwrite_salary_structure_amount": 0,
            })

    def create_benefit_ledger_entry(self):
        for component in self.accrual_arrears or []:
            if not component.salary_component or not component.amount:
                continue
            flexible = frappe.db.get_value(
                "Salary Component", component.salary_component, "is_flexible_benefit"
            )
            _insert_employee_benefit_ledger({
                "employee": self.employee,
                "employee_name": self.employee_name,
                "company": self.company,
                "payroll_period": self.payroll_period,
                "salary_component": component.salary_component,
                "transaction_type": "Accrual",
                "amount": component.amount,
                "reference_doctype": "Arrear",
                "reference_document": self.name,
                "remarks": "Accrual via Arrears",
                "flexible_benefit": flexible,
            })


@frappe.whitelist()
def inspect_payroll_adjustment_readiness(
    salary_slip: str,
    issue_type: str,
    payroll_date: str | None = None,
):
    company = frappe.db.get_value("Salary Slip", salary_slip, "company")
    if not company:
        frappe.throw(_("Salary Slip not found."))
    _authorize_company(company)
    if not frappe.has_permission("Salary Slip", "read", salary_slip):
        frappe.throw(_("You do not have permission to inspect this Salary Slip."), frappe.PermissionError)
    slip = frappe.get_doc("Salary Slip", salary_slip)
    if slip.docstatus != 1:
        return {"status": "SOURCE_PAYROLL_NOT_FINALIZED", "next_action": _("Submit the source payroll first.")}

    _validate_managed_source_slip(slip)
    if issue_type == "overpayment":
        return {
            "status": "RETRO_OVERPAYMENT_DECISION_REQUIRED",
            "next_action": _("Ask HR and Finance to approve a recovery method; no automatic deduction is created."),
        }
    if issue_type == "daily_wage":
        return {
            "status": "DAILY_WAGE_RETRO_ADJUSTMENT_REVIEW_REQUIRED",
            "next_action": _("Review the approved attendance correction and route a future-period adjustment. Do not reopen consumed attendance inputs."),
        }
    if issue_type not in ("lwp", "salary_structure"):
        frappe.throw(_("Select LWP reversal, salary structure change, Daily Wage review, or overpayment."))
    if not payroll_date or getdate(payroll_date) <= getdate(slip.end_date):
        return {"status": "FUTURE_PAYROLL_DATE_REQUIRED", "next_action": _("Choose a payroll date after the source Salary Slip period.")}
    if issue_type == "lwp" and not flt(slip.get("leave_without_pay")):
        return {"status": "ADJUSTMENT_NOT_APPLICABLE", "next_action": _("This Salary Slip has no LWP to reverse.")}
    if _target_payroll_has_started(slip.employee, slip.company, payroll_date):
        return {
            "status": "TARGET_PAYROLL_ALREADY_STARTED",
            "next_action": _("A non-cancelled target Salary Slip or active managed Payroll Entry already exists. Choose a later payroll date."),
        }
    if issue_type == "lwp":
        return {"status": "LWP_REVERSAL_AVAILABLE", "native_doctype": "Payroll Correction"}
    return {"status": "SALARY_ARREAR_AVAILABLE", "native_doctype": "Arrear"}
