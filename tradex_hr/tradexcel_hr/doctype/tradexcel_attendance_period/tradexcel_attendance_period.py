from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from tradex_hr.tradexcel_hr.attendance_payroll_boundary import (
    current_attendance_period_hash,
    inspect_attendance_integrity,
)


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
