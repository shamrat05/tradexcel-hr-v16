"""Selected-Employee authorization for HRMS' native Leave Control Panel."""

from __future__ import annotations

import frappe
from frappe import _
from workforce_suite.workforce_suite.bulk_execution_safety import private_bulk_results
from frappe.utils import getdate

from workforce_suite.workforce_suite.company_context import assert_company_access


def require_submitted_leave_policy(doc, _method=None) -> None:
    """A direct native assignment cannot activate an unapproved policy."""
    if not frappe.get_list(
        "Leave Policy", filters={"name": doc.leave_policy, "docstatus": 1},
        limit_page_length=1,
    ):
        frappe.throw(_("Submit the Leave Policy before assigning it."), frappe.ValidationError)


class WorkforceLeaveControlPanelMixin:
    """Keep native allocation and partial-result behavior after a scoped check."""

    def _assert_company_context(self, company: str) -> None:
        # Native HRMS users can operate this tool without Company read DocPerm.
        # Respect their native User Permissions without imposing Workforce's
        # explicit-Company configuration rule on a combined-role account.
        if {"HR User", "HR Manager"}.intersection(frappe.get_roles()):
            company_doc = frappe.get_doc("Company", company)
            if not frappe.permissions.has_user_permission(company_doc, ptype="read"):
                frappe.throw(_("You cannot use this Company."), frappe.PermissionError)
        else:
            assert_company_access(company, require_explicit_scope=True)

    def _validate_leave_context(self) -> None:
        if self.company:
            self._assert_company_context(self.company)
        if self.allocate_based_on_leave_policy and self.leave_policy:
            if not frappe.get_list(
                "Leave Policy", filters={"name": self.leave_policy, "docstatus": 1},
                limit_page_length=1,
            ):
                frappe.throw(_("Select a submitted Leave Policy."), frappe.ValidationError)
        if self.dates_based_on != "Leave Period" or not self.leave_period:
            return
        period = frappe.db.get_value(
            "Leave Period", self.leave_period, ["company", "is_active"], as_dict=True
        )
        if not period or not period.is_active:
            frappe.throw(_("Select an active Leave Period."), frappe.ValidationError)
        self._assert_company_context(period.company)
        if self.company and period.company != self.company:
            frappe.throw(_("The Leave Period must belong to the selected Company."), frappe.ValidationError)
        if not frappe.get_list("Leave Period", filters={"name": self.leave_period}, limit_page_length=1):
            frappe.throw(_("You cannot use this Leave Period."), frappe.PermissionError)

    @frappe.whitelist()
    def get_employees(self, advanced_filters: list | None = None) -> list:
        self._validate_leave_context()
        rows = super().get_employees(advanced_filters=advanced_filters or [])
        if not rows:
            return []
        from_date, to_date = self.get_from_to_date()
        employment_dates = {
            row.name: row for row in frappe.get_list(
                "Employee", filters={"name": ["in", [row.employee for row in rows]]},
                fields=["name", "date_of_joining", "relieving_date"],
                limit_page_length=len(rows),
            )
        }
        return [
            row for row in rows
            if (employment := employment_dates.get(row.employee))
            and not (to_date and employment.date_of_joining and getdate(employment.date_of_joining) > getdate(to_date))
            and not (from_date and employment.relieving_date and getdate(employment.relieving_date) < getdate(from_date))
        ]

    @frappe.whitelist(methods=["POST"])
    def allocate_leave(self, employees: list):
        # HRMS' preview uses permission-aware get_list, but its apply method
        # accepts client-supplied names. Validate the same native population at
        # apply time, including active status and existing allocation exclusion.
        self.validate_fields(employees)
        self._validate_leave_context()
        eligible = {row.employee for row in self.get_employees(advanced_filters=[])}
        if not set(employees).issubset(eligible):
            frappe.throw(
                _("Refresh the Employee list. A selected Employee is outside your permitted scope or is no longer eligible."),
                frappe.PermissionError,
            )
        with private_bulk_results():
            return super().allocate_leave(employees)

    @frappe.whitelist()
    def get_latest_leave_period(self):
        from erpnext import get_default_company

        company = self.company or get_default_company()
        if not company:
            return None
        if self.company:
            self._assert_company_context(company)
        else:
            # The native form asks for its default period before an operator
            # selects Company. A site-wide default outside this user's scope
            # should leave that field empty, not make the form unusable.
            try:
                self._assert_company_context(company)
            except frappe.PermissionError:
                return None
        return super().get_latest_leave_period()
