from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from workforce_suite.workforce_suite.field_attendance import calculate_allowance


class WorkforceFieldDuty(Document):
    def validate(self):
        company = frappe.db.get_value("Employee", self.employee, "company")
        if not company or company != self.company:
            frappe.throw("Employee must belong to the selected company")
        if self.end_time and self.start_time and self.end_time < self.start_time:
            frappe.throw("Duty end time cannot be before start time")
        for stop in self.stops or []:
            if stop.distance_km is not None and float(stop.distance_km) < 0:
                frappe.throw("Duty stop distance cannot be negative")
        result = calculate_allowance(
            self.allowance_mode or "None",
            distance_km=self.approved_distance_km or sum(float(row.distance_km or 0) for row in self.stops or []),
            rate_per_km=self.rate_per_km or 0,
            fixed_amount=self.fixed_area_amount or 0,
            multiplier=self.allowance_multiplier or 1,
        )
        if self.status in {"Approved", "In Progress", "Completed"}:
            self.approved_distance_km = result["distance_km"]
            self.approved_allowance_amount = result["amount"]

    def on_submit(self):
        self.status = "Approved"
        self.approved_by = frappe.session.user
        self.approved_on = now_datetime()
        self.db_update()

    def on_cancel(self):
        self.status = "Cancelled"
        self.db_update()
