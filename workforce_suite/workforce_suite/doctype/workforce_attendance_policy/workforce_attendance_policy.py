from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class WorkforceAttendancePolicy(Document):
    def validate(self):
        if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
            frappe.throw("Effective To cannot be before Effective From")
        if self.employee and frappe.db.get_value("Employee", self.employee, "company") != self.company:
            frappe.throw("Employee must belong to the selected company")
        if self.tracking_interval_minutes and not 1 <= int(self.tracking_interval_minutes) <= 1440:
            frappe.throw("Tracking interval must be between 1 and 1,440 minutes")
        if not 1 <= int(self.offline_max_age_hours if self.offline_max_age_hours is not None else 72) <= 720:
            frappe.throw("Maximum offline age must be between 1 and 720 hours")
        if not 0 <= int(self.offline_trust_window_minutes if self.offline_trust_window_minutes is not None else 5) <= 1440:
            frappe.throw("Receipt-time trust window must be between 0 and 1,440 minutes")
        if self.retention_days is not None and not 1 <= int(self.retention_days) <= 3650:
            frappe.throw("Evidence retention must be between 1 and 3,650 days")
        if float(self.allowance_multiplier or 0) < 0:
            frappe.throw("Allowance multiplier cannot be negative")
        if self.allowance_mode == "Per Km" and float(self.rate_per_km or 0) <= 0:
            frappe.throw("Per Km allowance requires a positive rate")
        if self.allowance_mode == "Fixed Area" and float(self.fixed_area_amount or 0) <= 0:
            frappe.throw("Fixed Area allowance requires a positive amount")
        if self.allowance_mode != "None" and not self.allowance_salary_component:
            frappe.throw("Select the Salary Component used for travel allowance")

    def on_submit(self):
        self.enabled = 1
        self.db_update()

    def on_cancel(self):
        self.enabled = 0
        self.db_update()
