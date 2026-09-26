"""Restrict unsupported native Shift Assignment Tool actions for Tradexcel roles."""

from __future__ import annotations

import frappe
from frappe import _
from tradex_hr.tradexcel_hr.bulk_execution_safety import private_bulk_results


TRADESCEL_SHIFT_OPERATOR_ROLES = {
    "Tradexcel HR Manager",
    "Tradexcel HR/Attendance Officer",
}


def _tradexcel_only_operator():
    roles = set(frappe.get_roles())
    return bool(TRADESCEL_SHIFT_OPERATOR_ROLES & roles) and not bool(
        {"HR User", "HR Manager"} & roles
    )


class TradexcelShiftAssignmentToolMixin:
    """Keep native processing while closing selected-Employee scope bypasses."""

    def _check_tradexcel_shift_action(self) -> None:
        if not _tradexcel_only_operator():
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
            [
                "shift_schedule"
                if self.action == "Assign Shift Schedule"
                else "shift_type",
                "company",
                "start_date",
            ],
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
        self.check_permission("read")
        self._check_tradexcel_shift_action()
        return super().get_employees(advanced_filters=advanced_filters)

    @frappe.whitelist(methods=["POST"])
    def bulk_assign(self, employees: list):
        self._check_tradexcel_shift_action()
        self.check_permission("read")
        if self.action in {"Assign Shift", "Assign Shift Schedule"}:
            self._validate_selected_employees(employees)
        return super().bulk_assign(employees=employees)

    def _bulk_assign(self, employees: list):
        self._check_tradexcel_shift_action()
        self.check_permission("read")
        if self.action in {"Assign Shift", "Assign Shift Schedule"}:
            # Queued jobs use this same method. Re-resolve scope/eligibility at
            # execution time so User Permission or Employee state changes made
            # after queueing cannot widen the operation.
            self._validate_selected_employees(employees)
        with private_bulk_results():
            return super()._bulk_assign(employees)

    def _validate_shift_requests(self, shift_requests, status):
        self.check_permission("read")
        if _tradexcel_only_operator():
            frappe.throw(
                _(
                    "Bulk Shift Request processing is not enabled for Tradexcel operator roles."
                ),
                frappe.PermissionError,
            )
        if self.action != "Process Shift Requests" or status not in {
            "Approved",
            "Rejected",
        }:
            frappe.throw(_("Choose Approve or Reject from Process Shift Requests."))
        if not isinstance(shift_requests, list) or not shift_requests:
            frappe.throw(_("Select at least one Shift Request."))
        eligible = {row.name: row.employee for row in super().get_employees()}
        for row in shift_requests:
            if (
                not isinstance(row, dict)
                or not row.get("shift_request")
                or eligible.get(row["shift_request"]) != row.get("employee")
            ):
                frappe.throw(
                    _(
                        "Refresh the request list. A selected request is outside your permitted scope or is no longer eligible."
                    ),
                    frappe.PermissionError,
                )
            request = frappe.get_doc("Shift Request", row["shift_request"])
            request.check_permission("write")
            request.check_permission("submit")

    @frappe.whitelist(methods=["POST"])
    def bulk_process_shift_requests(self, shift_requests: list, status: str):
        self._validate_shift_requests(shift_requests, status)
        return super().bulk_process_shift_requests(
            shift_requests=shift_requests, status=status
        )

    def _bulk_process_shift_requests(self, shift_requests: list, status: str):
        self._validate_shift_requests(shift_requests, status)
        with private_bulk_results():
            return super()._bulk_process_shift_requests(shift_requests, status)
