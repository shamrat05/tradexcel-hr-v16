import frappe
from frappe.model.document import Document


class TradexcelBiometricDevice(Document):
    def validate(self):
        self.device_code = str(self.device_code or "").strip()
        self.device_serial = str(self.device_serial or "").strip()
        if not self.device_code:
            frappe.throw("Device Code is required")

        if self.device_serial:
            existing = frappe.db.get_value(
                "Tradexcel Biometric Device", {"device_serial": self.device_serial}, "name"
            )
            if existing and existing != self.name:
                frappe.throw(
                    f"Device Serial {self.device_serial} is already registered as {existing}"
                )
        elif self.enabled:
            frappe.throw("Enter the real terminal serial before enabling live sync")
