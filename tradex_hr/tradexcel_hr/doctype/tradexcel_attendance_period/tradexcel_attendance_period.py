from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from tradex_hr.tradexcel_hr.attendance_payroll_boundary import (
    current_attendance_period_hash,
    inspect_attendance_integrity,
)


def _salary_slips_using_input(additional_salary: str) -> list[dict]:
    return frappe.db.sql(
        """
        SELECT ss.name, ss.docstatus
        FROM `tabSalary Slip` ss
        INNER JOIN `tabSalary Detail` sd ON sd.parent = ss.name
        WHERE sd.parenttype = 'Salary Slip'
          AND sd.additional_salary = %(additional_salary)s
          AND ss.docstatus IN (0, 1)
        """,
        {"additional_salary": additional_salary},
        as_dict=True,
    )


def _retire_daily_wage_inputs(period_name: str) -> None:
    """Disable old derived inputs before a period can be revised.

    A submitted Salary Slip may already have consumed the input, and even a
    draft slip can later be submitted with the old amount. Both cases require
    payroll reconciliation rather than silently changing financial history.
    """
    inputs = frappe.get_all(
        "Additional Salary",
        filters={
            "ref_doctype": "Tradexcel Attendance Period",
            "ref_docname": period_name,
            "custom_tradex_payroll_input_key": ["like", f"DAILY-WAGE:{period_name}:r%"],
            "docstatus": ["<", 2],
        },
        fields=["name", "docstatus", "disabled"],
    )
    for item in inputs:
        users = _salary_slips_using_input(item["name"])
        if users:
            names = ", ".join(row["name"] for row in users[:5])
            frappe.throw(
                _(
                    "Attendance Period {0} has already been used by Salary Slip(s) {1}. "
                    "Use the post-payroll adjustment review instead of reopening it."
                ).format(period_name, names)
            )
        if not item["disabled"]:
            frappe.db.set_value("Additional Salary", item["name"], "disabled", 1)


class TradexcelAttendancePeriod(Document):
    def validate(self):
        if self.from_date and self.to_date and self.from_date > self.to_date:
            frappe.throw(_("To Date cannot be before From Date"))
        if self.company and self.from_date and self.to_date:
            filters = {
                "company": self.company,
                "from_date": self.from_date,
                "to_date": self.to_date,
            }
            if not self.is_new():
                filters["name"] = ["!=", self.name]
            if frappe.db.exists("Tradexcel Attendance Period", filters):
                frappe.throw(_("An Attendance Period already exists for this company and exact date range"))

        previous_status = None
        if self.name and not self.is_new():
            previous_status = frappe.db.get_value("Tradexcel Attendance Period", self.name, "status")
        if previous_status and self.status != previous_status and not (
            self.get("_finalize_context") or self.get("_reopen_context")
        ):
            frappe.throw(_("Use Finalize Attendance or Reopen to change the period status"))

        if self.status == "Finalized":
            if not self.get("_finalize_context"):
                frappe.throw(_("Use the Finalize Attendance action to finalize this period"))
            if not self.attendance_hash:
                frappe.throw(_("A finalized period must have a native attendance version"))

    def finalize_period(self):
        self.check_permission("write")
        result = inspect_attendance_integrity(self.company, self.from_date, self.to_date)
        if result["status"] != "READY":
            reasons = "; ".join(item.get("reason", item.get("code", "Unknown issue")) for item in result["blockers"][:8])
            frappe.throw(_("Attendance cannot be finalized yet: {0}").format(reasons))
        from tradex_hr.tradexcel_hr.working_time_compliance import inspect_working_time_compliance
        legal_review = inspect_working_time_compliance(self.company, self.from_date, self.to_date)
        statutory_blocks = [
            finding
            for employee in legal_review.get("employees", [])
            for finding in employee.get("findings", [])
            if finding["severity"] == "block"
        ]
        if statutory_blocks:
            reasons = "; ".join(item["code"] for item in statutory_blocks[:8])
            frappe.throw(_("Working-time review must be resolved before Attendance finalization: {0}").format(reasons))
        from tradex_hr.tradexcel_hr.flexible_work_records import validate_operational_day_overrides
        override_findings = validate_operational_day_overrides(self.company, self.from_date, self.to_date)
        if override_findings:
            reasons = "; ".join(item["code"] for item in override_findings[:8])
            frappe.throw(_("Operational-day pay decisions need a current preview before Attendance finalization: {0}").format(reasons))
        self.status = "Finalized"
        self.revision = (self.revision or 0) + 1
        self.attendance_hash = current_attendance_period_hash(self.company, self.from_date, self.to_date)
        self.finalized_by = frappe.session.user
        self.finalized_at = now_datetime()
        self._finalize_context = True
        self.save()
        return {"status": self.status, "revision": self.revision, "attendance_hash": self.attendance_hash}

    def reopen_period(self):
        self.check_permission("write")
        if self.status != "Finalized":
            frappe.throw(_("Only a finalized attendance period can be reopened"))
        _retire_daily_wage_inputs(self.name)
        self.status = "Reopened"
        self._reopen_context = True
        self.save()
        return {"status": self.status, "revision": self.revision}


@frappe.whitelist()
def finalize_attendance_period(name: str):
    return frappe.get_doc("Tradexcel Attendance Period", name).finalize_period()


@frappe.whitelist()
def reopen_attendance_period(name: str):
    return frappe.get_doc("Tradexcel Attendance Period", name).reopen_period()
