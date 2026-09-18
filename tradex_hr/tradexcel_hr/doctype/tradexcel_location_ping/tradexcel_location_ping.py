import frappe
from frappe.model.document import Document

from tradex_hr.tradexcel_hr.field_attendance import validate_coordinates


class TradexcelLocationPing(Document):
    def validate(self):
        validate_coordinates(self.latitude, self.longitude)
        if self.accuracy_m is not None and float(self.accuracy_m) < 0:
            frappe.throw("GPS accuracy cannot be negative")
        if frappe.db.get_value("Employee", self.employee, "company") != self.company:
            frappe.throw("Employee and company do not match")
        if not frappe.db.exists("Tradexcel Field Duty", {"name": self.field_duty, "employee": self.employee}):
            frappe.throw("Field Duty does not belong to the employee")
