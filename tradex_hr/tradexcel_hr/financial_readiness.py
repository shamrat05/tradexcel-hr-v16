"""Read-only financial checks for managed native payroll drafts."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.utils import getdate

from tradex_hr.tradexcel_hr.native_payroll import MANAGED_RUN_FIELD


def _money(value):
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def _tax_exception_findings(company, start, end):
    rows = frappe.get_all(
        "Tradexcel Policy Exception",
        filters={"company": company, "exception_type": "Tax", "docstatus": ["<", 2]},
        fields=["name", "docstatus", "effective_from", "effective_to"],
    )
    findings = []
    for row in rows:
        if row.effective_from and getdate(row.effective_from) > getdate(end):
            continue
        if row.effective_to and getdate(row.effective_to) < getdate(start):
            continue
        findings.append({
            "code": "TAX_EXCEPTION_REVIEW_REQUIRED",
            "reference": row.name,
            "reason": _("Tax Policy Exception {0} needs review against native Income Tax Slab configuration.").format(row.name),
            "severity": "BLOCKER" if int(row.docstatus or 0) == 1 else "WARNING",
        })
    return findings


def _tax_configuration_findings(entry, slips, details, components, assignments_by_slip):
    tax_components = {
        name for name, item in components.items()
        if int(item.get("variable_based_on_taxable_salary") or 0)
    }
    taxable_earnings = any(
        detail.parentfield == "earnings"
        and int(components.get(detail.salary_component, {}).get("is_tax_applicable") or 0)
        for detail in details
    )
    if not tax_components:
        if taxable_earnings:
            return [{
                "code": "TAX_COMPONENT_MISSING",
                "reason": _("Taxable salary exists, but no native tax calculation Salary Component is configured."),
                "severity": "BLOCKER",
            }]
        return []

    # Match the native SSA validator: an assignment needs a slab when its
    # Salary Structure has a variable tax deduction component. HRMS also has a
    # company-level fallback while constructing a new Salary Slip; that does
    # not change the per-structure SSA requirement checked here.
    from hrms.payroll.doctype.salary_structure_assignment.salary_structure_assignment import (
        get_tax_component,
    )

    structures = {slip.salary_structure for slip in slips if slip.salary_structure}
    taxable_structures = {
        structure for structure in structures if get_tax_component(structure)
    }
    taxable_slips = [slip for slip in slips if slip.salary_structure in taxable_structures]
    if not taxable_slips:
        return []

    from hrms.payroll.doctype.payroll_period.payroll_period import get_payroll_period

    period = get_payroll_period(entry.start_date, entry.end_date, entry.company)
    if not period:
        return [{
            "code": "TAX_PERIOD_MISSING",
            "reason": _("No native Payroll Period covers this payroll."),
            "severity": "BLOCKER",
        }]

    findings = []
    for slip in taxable_slips:
        if slip.current_payroll_period != period.name:
            findings.append({
                "code": "TAX_PERIOD_MISSING",
                "employee": slip.employee,
                "reason": _("Native tax calculation did not resolve Payroll Period {0} for {1}.").format(
                    period.name, slip.employee
                ),
                "severity": "BLOCKER",
            })
        assignment = assignments_by_slip.get(slip.name)
        if not assignment:
            findings.append({
                "code": "TAX_ASSIGNMENT_MISSING",
                "employee": slip.employee,
                "reason": _("Salary Structure Assignment is missing for {0}.").format(slip.employee),
                "severity": "BLOCKER",
            })
            continue
        slab_name = assignment.income_tax_slab
        if not slab_name:
            findings.append({
                "code": "TAX_ASSIGNMENT_MISSING",
                "employee": slip.employee,
                "reason": _("No Income Tax Slab is selected on the Salary Structure Assignment for {0}.").format(
                    slip.employee
                ),
                "severity": "BLOCKER",
            })
            continue
        slab = frappe.db.get_value(
            "Income Tax Slab", slab_name,
            ["company", "effective_from", "disabled", "docstatus", "custom_tradex_review_status"],
            as_dict=True,
        )
        reason = None
        code = "TAX_SLAB_MISSING"
        if not slab or slab.company != entry.company:
            reason = _("Income Tax Slab {0} is missing or belongs to another company.").format(slab_name)
        elif int(slab.docstatus or 0) != 1 or int(slab.disabled or 0):
            reason = _("Income Tax Slab {0} is not submitted and active.").format(slab_name)
        elif getdate(slab.effective_from) > getdate(period.start_date):
            reason = _("Income Tax Slab {0} is not effective for this Payroll Period.").format(slab_name)
        elif slab.custom_tradex_review_status != "Approved":
            code = "TAX_SLAB_UNAPPROVED"
            reason = _("Income Tax Slab {0} needs an authorized source review.").format(slab_name)
        if reason:
            findings.append({
                "code": code,
                "employee": slip.employee,
                "reason": reason,
                "severity": "BLOCKER",
            })
    return findings


def _previous_slips(company, before_date):
    rows = frappe.db.sql(
        """SELECT s.employee, s.name, s.net_pay, s.end_date
        FROM `tabSalary Slip` s
        INNER JOIN (
            SELECT employee, MAX(end_date) AS end_date
            FROM `tabSalary Slip`
            WHERE company = %(company)s AND docstatus = 1 AND end_date < %(before_date)s
            GROUP BY employee
        ) p ON p.employee = s.employee AND p.end_date = s.end_date
        WHERE s.company = %(company)s AND s.docstatus = 1""",
        {"company": company, "before_date": before_date}, as_dict=True,
    )
    return {row.employee: row for row in rows}


def _component_exception_provenance(employee, day, actual_earnings, structure_components, rules):
    from tradex_hr.tradexcel_hr.component_exceptions import resolve_component

    traces = []
    for component in sorted(set(actual_earnings) | set(structure_components)):
        rule = resolve_component(employee, day, rules, component)
        if not rule:
            continue
        action = rule.get("component_action")
        applied = (
            action == "Exclude" and component in structure_components and component not in actual_earnings
        ) or (
            action == "Override Amount" and component in actual_earnings
            and _money(actual_earnings[component]) == _money(rule.get("component_amount"))
        )
        if applied:
            traces.append({
                "component": component,
                "source": rule.get("name"),
                "action": action,
                "amount": _money(rule.get("component_amount")) if action == "Override Amount" else None,
            })
    return traces


def inspect_payroll_financial_readiness(payroll_entry, *, allow_partial_submission=False):
    """Inspect a managed Payroll Entry and real draft Salary Slips without writes."""
    entry = frappe.get_doc("Payroll Entry", payroll_entry) if isinstance(payroll_entry, str) else payroll_entry
    from tradex_hr.tradexcel_hr.company_context import assert_company_access
    assert_company_access(entry.company, require_explicit_scope=True)

    blockers, warnings = [], []

    def add(code, reason, employee=None, reference=None, severity="BLOCKER"):
        row = {"code": code, "reason": reason, "severity": severity}
        if employee:
            row["employee"] = employee
        if reference:
            row["reference"] = reference
        (warnings if severity == "WARNING" else blockers).append(row)

    if not entry.get(MANAGED_RUN_FIELD):
        add("UNMANAGED_PAYROLL_ENTRY", _("This Payroll Entry was not prepared through Payroll Readiness."))
    if int(entry.docstatus or 0) != 1:
        add("PAYROLL_ENTRY_NOT_SUBMITTED", _("Submit the prepared Payroll Entry for review before financial checks."))
    native_submission_worker = bool(getattr(frappe.flags, "via_payroll_entry", False))
    if entry.status == "Failed" and not entry.salary_slips_created:
        add("SALARY_SLIP_CREATION_FAILED", _("Native Salary Slip creation failed. Open Payroll Entry for its error details."))
    elif (entry.status == "Queued" and not native_submission_worker) or not entry.salary_slips_created:
        add("SALARY_SLIP_CREATION_INCOMPLETE", _("Native Salary Slip creation has not completed."))

    expected = {row.employee for row in entry.get("employees", []) if row.get("employee")}
    expected_drafts = expected
    if allow_partial_submission:
        submitted_employees = set(frappe.get_all(
            "Salary Slip",
            filters={"payroll_entry": entry.name, "docstatus": 1},
            fields=["employee"],
            pluck="employee",
        ))
        expected_drafts = expected - submitted_employees
    slips = frappe.get_all(
        "Salary Slip", filters={"payroll_entry": entry.name, "docstatus": 0},
        fields=["name", "employee", "company", "start_date", "end_date", "salary_structure",
                "current_payroll_period", "gross_pay", "total_deduction", "net_pay"],
        order_by="employee asc",
    )
    by_employee = defaultdict(list)
    for slip in slips:
        by_employee[slip.employee].append(slip)
    if set(by_employee) != expected_drafts or any(len(items) != 1 for items in by_employee.values()):
        add("DRAFT_SLIP_UNIVERSE_MISMATCH", _("Draft Salary Slips do not match the Payroll Entry employee list."))
    if not slips:
        add("DRAFT_SLIP_MISSING", _("No native draft Salary Slips are available for review."))
    for slip in slips:
        if slip.company != entry.company or getdate(slip.start_date) != getdate(entry.start_date) or getdate(slip.end_date) != getdate(entry.end_date):
            add("DRAFT_SLIP_UNIVERSE_MISMATCH", _("Salary Slip {0} has a different company or payroll period.").format(slip.name), employee=slip.employee)

    details = []
    if slips:
        details = frappe.get_all(
            "Salary Detail",
            filters={"parent": ["in", [row.name for row in slips]], "parenttype": "Salary Slip",
                     "parentfield": ["in", ["earnings", "deductions"]]},
            fields=["parent", "parentfield", "salary_component", "amount", "do_not_include_in_total",
                    "do_not_include_in_accounts", "additional_salary"],
        )
    names = {row.salary_component for row in details if row.salary_component}
    structures = sorted({row.salary_structure for row in slips if row.salary_structure})
    employees = sorted({row.employee for row in slips if row.employee})
    employee_rows = frappe.get_all(
        "Employee", filters={"name": ["in", employees]},
        fields=["name", "company", "branch", "department", "designation", "date_of_joining"],
    ) if employees else []
    employee_context = {row.name: row for row in employee_rows}
    assignment_candidates = frappe.get_all(
        "Salary Structure Assignment",
        filters={"employee": ["in", employees], "salary_structure": ["in", structures],
                 "from_date": ["<=", entry.end_date], "docstatus": 1},
        fields=["name", "employee", "salary_structure", "from_date", "income_tax_slab"],
        order_by="from_date desc",
    ) if employees and structures else []
    assignments_by_slip = {}
    for slip in slips:
        employee = employee_context.get(slip.employee)
        joining_date = getdate(employee.date_of_joining) if employee and employee.date_of_joining else None
        actual_start = (
            joining_date
            if joining_date and getdate(slip.start_date) < joining_date <= getdate(slip.end_date)
            else getdate(slip.start_date)
        )
        assignments_by_slip[slip.name] = next((
            row for row in assignment_candidates
            if row.employee == slip.employee
            and row.salary_structure == slip.salary_structure
            and getdate(row.from_date) <= actual_start
        ), None)
    if slips:
        # HRMS uses this method when a structure has no tax component. Using
        # the same resolver covers valid zero-amount tax rows omitted from the
        # Salary Detail table without introducing a separate company policy.
        native_slip = frappe.get_doc({"doctype": "Salary Slip", "company": entry.company})
        names.update(native_slip.get_tax_components() or [])
    names = sorted(names)
    components = {}
    if names:
        components = {row.name: row for row in frappe.get_all(
            "Salary Component", filters={"name": ["in", names]},
            fields=["name", "variable_based_on_taxable_salary", "is_income_tax_component", "is_tax_applicable", "statistical_component", "type"],
        )}

    payable = entry.get("payroll_payable_account")
    info = frappe.db.get_value("Account", payable, ["account_type", "company", "is_group", "disabled"], as_dict=True) if payable else None
    if (
        not info or info.company != entry.company or info.account_type != "Payable"
        or int(info.is_group or 0) or int(info.disabled or 0)
    ):
        add("PAYROLL_PAYABLE_INVALID", _("Payroll payable must be a company account with Account Type Payable."), reference=payable)

    # Native accrual accounting assigns Payroll Entry.cost_center to the
    # Payroll Payable credit line. Employee/component cost-center validation
    # below does not cover that company-level balance-sheet line.
    payable_cost_center = entry.get("cost_center")
    payable_center_info = (
        frappe.db.get_value(
            "Cost Center", payable_cost_center,
            ["company", "is_group", "disabled"], as_dict=True,
        )
        if payable_cost_center else None
    )
    if (
        not payable_center_info
        or payable_center_info.company != entry.company
        or int(payable_center_info.is_group or 0)
        or int(payable_center_info.disabled or 0)
    ):
        add(
            "ACCOUNTING_DIMENSION_MISSING",
            _("A valid company payroll cost center is required for the payable accounting line."),
            reference="Cost Center",
        )

    # Match HRMS Payroll Entry.get_salary_components(): only components included
    # in accounting are required to have mappings.
    accounting_components = {
        row.salary_component for row in details
        if row.salary_component and (
            not int(row.do_not_include_in_total or 0)
            or not int(row.do_not_include_in_accounts or 0)
        ) and _money(row.amount) != 0
        and not int((components.get(row.salary_component) or {}).get("statistical_component") or 0)
    }
    employees_by_component = defaultdict(set)
    for row in details:
        if row.salary_component and _money(row.amount) != 0:
            employees_by_component[row.salary_component].add(row.parent)
    employee_by_slip = {row.name: row.employee for row in slips}
    component_accounts = {}
    for component in sorted(accounting_components):
        account = frappe.db.get_value(
            "Salary Component Account", {"parent": component, "company": entry.company}, "account"
        )
        if not account:
            for parent in employees_by_component[component]:
                add("COMPONENT_ACCOUNT_MISSING", _("Salary Component {0} has no company account mapping.").format(component), employee=employee_by_slip.get(parent), reference=component)
            continue
        component_accounts[component] = account
        account_info = frappe.db.get_value(
            "Account", account, ["company", "root_type", "is_group", "disabled"], as_dict=True
        )
        if (
            not account_info or account_info.company != entry.company
            or int(account_info.is_group or 0) or int(account_info.disabled or 0)
        ):
            for parent in employees_by_component[component]:
                add("COMPONENT_ACCOUNT_MISSING", _("The account mapped to {0} is not a valid account for this company.").format(component), employee=employee_by_slip.get(parent), reference=component)

    for slip in slips:
        centers = entry.get_payroll_cost_centers_for_employee(slip.employee, slip.salary_structure)
        try:
            percentages = [Decimal(str(value or 0)) for value in centers.values()]
        except (InvalidOperation, TypeError, ValueError):
            percentages = []
        invalid = (
            not centers
            or len(percentages) != len(centers)
            or any(value < 0 for value in percentages)
            or abs(sum(percentages, Decimal("0")) - Decimal("100")) > Decimal("0.0001")
        )
        if not invalid:
            for cost_center in centers:
                info = frappe.db.get_value("Cost Center", cost_center, ["company", "is_group", "disabled"], as_dict=True) if cost_center else None
                if not info or info.company != entry.company or int(info.is_group or 0) or int(info.disabled or 0):
                    invalid = True
                    break
        if invalid:
            add("ACCOUNTING_DIMENSION_MISSING", _("A valid cost center could not be resolved for {0}.").format(slip.employee), employee=slip.employee, reference="Cost Center")

    if component_accounts:
        from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_checks_for_pl_and_bs_accounts

        dimensions = get_checks_for_pl_and_bs_accounts()
        if dimensions:
            from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions

            dimension_doctypes = {
                dimension.fieldname: dimension.document_type
                for dimension in get_accounting_dimensions(as_list=False)
            }
            for component, account in component_accounts.items():
                root_type = frappe.db.get_value("Account", account, "root_type")
                for dimension in dimensions:
                    if dimension.company not in (None, "", entry.company):
                        continue
                    required = dimension.mandatory_for_pl if root_type in {"Income", "Expense"} else dimension.mandatory_for_bs
                    value = dimension.default_dimension or entry.get(dimension.fieldname)
                    if not required:
                        continue
                    target_doctype = dimension_doctypes.get(dimension.fieldname)
                    if not value:
                        add("ACCOUNTING_DIMENSION_MISSING", _("{0} is required for payroll accounting.").format(dimension.label), reference=dimension.fieldname)
                    elif not target_doctype or not frappe.db.exists(target_doctype, value):
                        add("ACCOUNTING_DIMENSION_MISSING", _("{0} points to a missing or unavailable record.").format(dimension.label), reference=dimension.fieldname)
                    elif frappe.get_meta(target_doctype).has_field("company"):
                        company = frappe.db.get_value(target_doctype, value, "company")
                        if company and company != entry.company:
                            add("ACCOUNTING_DIMENSION_MISSING", _("{0} belongs to another company.").format(dimension.label), reference=dimension.fieldname)

    by_slip = defaultdict(list)
    for detail in details:
        by_slip[detail.parent].append(detail)
    component_rules = []
    if slips:
        from tradex_hr.tradexcel_hr.component_exceptions import load_component_rules

        component_rules = load_component_rules(entry.company)
    structure_components = defaultdict(set)
    if slips:
        if structures:
            for item in frappe.get_all(
                "Salary Detail",
                filters={"parent": ["in", structures], "parenttype": "Salary Structure",
                         "parentfield": "earnings"},
                fields=["parent", "salary_component"],
            ):
                structure_components[item.parent].add(item.salary_component)
    additional_salary_names = sorted({row.additional_salary for row in details if row.additional_salary})
    additional_salary_info = {}
    if additional_salary_names:
        additional_salary_info = {
            row.name: row for row in frappe.get_all(
                "Additional Salary", filters={"name": ["in", additional_salary_names]},
                fields=["name", "custom_tradex_payroll_input_key", "ref_doctype"],
            )
        }
    totals = {key: Decimal("0.00") for key in (
        "gross", "deductions", "net", "daily_wage", "overtime", "income_tax", "additional_salary"
    )}
    prior = _previous_slips(entry.company, entry.start_date) if slips else {}
    slip_results = []
    for slip in slips:
        gross, deductions, net = _money(slip.gross_pay), _money(slip.total_deduction), _money(slip.net_pay)
        if net < 0:
            add("NEGATIVE_NET_PAY", _("Net pay is negative after deductions."), employee=slip.employee)
        if gross - deductions != net:
            add("SLIP_TOTAL_MISMATCH", _("Salary Slip gross, deductions, and net do not reconcile."), employee=slip.employee)
        tax, daily, overtime, additional = Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00")
        for detail in by_slip[slip.name]:
            component = components.get(detail.salary_component) or {}
            amount = _money(detail.amount)
            if detail.parentfield == "deductions" and (
                int(component.get("variable_based_on_taxable_salary") or 0)
                or int(component.get("is_income_tax_component") or 0)
            ):
                tax += amount
            if detail.additional_salary and detail.parentfield == "earnings":
                extra = additional_salary_info.get(detail.additional_salary)
                additional += amount
                if extra and extra.custom_tradex_payroll_input_key:
                    daily += amount
                elif extra and extra.ref_doctype and "overtime" in extra.ref_doctype.casefold():
                    overtime += amount
        totals["gross"] += gross
        totals["deductions"] += deductions
        totals["net"] += net
        totals["daily_wage"] += daily
        totals["overtime"] += overtime
        totals["income_tax"] += tax
        totals["additional_salary"] += additional
        previous = prior.get(slip.employee)
        previous_net = _money(previous.net_pay) if previous else None
        delta = net - previous_net if previous_net is not None else None
        percent = (delta / previous_net * 100) if previous_net else None
        actual_earnings = {
            row.salary_component: row.amount for row in by_slip[slip.name]
            if row.parentfield == "earnings"
        }
        provenance = _component_exception_provenance(
            employee_context.get(slip.employee), entry.start_date, actual_earnings,
            structure_components.get(slip.salary_structure, set()), component_rules,
        ) if component_rules else []
        slip_results.append({
            "employee": slip.employee, "salary_slip": slip.name, "gross": gross,
            "deductions": deductions, "net": net, "income_tax": tax,
            "previous_net": previous_net, "net_variance": delta, "net_variance_percent": percent,
            "component_exceptions": provenance, "status": "READY",
        })

    for item in _tax_exception_findings(entry.company, entry.start_date, entry.end_date):
        add(item["code"], item["reason"], reference=item["reference"], severity=item["severity"])
    for item in _tax_configuration_findings(entry, slips, details, components, assignments_by_slip):
        add(item["code"], item["reason"], employee=item.get("employee"))

    global_blocker = any(not row.get("employee") for row in blockers)
    for result in slip_results:
        if global_blocker or any(row.get("employee") == result["employee"] for row in blockers):
            result["status"] = "BLOCKED"
        elif warnings:
            result["status"] = "REVIEW"
    return {
        "status": "BLOCKED" if blockers else "READY", "blockers": blockers, "warnings": warnings,
        "employee_count": len(expected), "salary_slip_count": len(slips),
        "totals": totals, "slips": slip_results,
    }


def validate_payroll_financial_readiness_before_approval(doc, method=None):
    if doc.get(MANAGED_RUN_FIELD) and doc.workflow_state in {
        "Tradexcel Payroll Pending Director Approval", "Tradexcel Payroll Approved"
    }:
        result = inspect_payroll_financial_readiness(doc)
        if result["status"] != "READY":
            reason = result["blockers"][0]["reason"] if result["blockers"] else _("Financial checks need review.")
            frappe.throw(_("Payroll financial readiness is blocked: {0}").format(reason), title=_("Payroll Financial Review Required"))
