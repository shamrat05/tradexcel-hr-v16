"""Restrict unsupported native Shift Assignment Tool actions for Tradexcel roles."""

from __future__ import annotations

import frappe
from frappe import _


TRADESCEL_SHIFT_OPERATOR_ROLES = {
    "Tradexcel HR Manager",
    "Tradexcel HR/Attendance Officer",
}


class TradexcelShiftAssignmentToolMixin:
    """Keep native processing while closing selected-Employee scope bypasses."""

    def _check_tradexcel_shift_action(self) -> None:
        if not TRADESCEL_SHIFT_OPERATOR_ROLES.intersection(frappe.get_roles()):
            return
        if self.action != "Assign Shift":
            frappe.throw(
                _("This bulk action is not enabled for your role. Use Assign Shift."),
                frappe.PermissionError,
            )

    def _validate_selected_employees(self, employees: list) -> None:
        from hrms.hr.utils import validate_bulk_tool_fields

        validate_bulk_tool_fields(
            self,
            ["shift_type", "company", "start_date"],
            employees,
            "start_date",
            "end_date",
        )
        eligible = {row.employee for row in super().get_employees()}
        if not set(employees).issubset(eligible):
            frappe.throw(
                _(
                    "Refresh the Employee list. One or more selected Employees are outside your "
                    "permitted scope or are no longer eligible for these dates."
                ),
                frappe.PermissionError,
            )

    @frappe.whitelist()
    def get_employees(self, advanced_filters: list | None = None) -> list:
        self._check_tradexcel_shift_action()
        return super().get_employees(advanced_filters=advanced_filters)

    @frappe.whitelist(methods=["POST"])
    def bulk_assign(self, employees: list):
        self._check_tradexcel_shift_action()
        if self.action == "Assign Shift":
            self._validate_selected_employees(employees)
        return super().bulk_assign(employees=employees)

    def _bulk_assign(self, employees: list):
        self._check_tradexcel_shift_action()
        if self.action == "Assign Shift":
            # Queued jobs use this same method. Re-resolve scope/eligibility at
            # execution time so User Permission or Employee state changes made
            # after queueing cannot widen the operation.
            self._validate_selected_employees(employees)
        return super()._bulk_assign(employees)

    @frappe.whitelist(methods=["POST"])
    def bulk_process_shift_requests(self, shift_requests: list, status: str):
        if TRADESCEL_SHIFT_OPERATOR_ROLES.intersection(frappe.get_roles()):
            frappe.throw(
                _("Bulk Shift Request processing is not enabled for Tradexcel operator roles."),
                frappe.PermissionError,
            )
        return super().bulk_process_shift_requests(shift_requests=shift_requests, status=status)
