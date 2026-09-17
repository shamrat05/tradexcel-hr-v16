from __future__ import annotations

import hashlib

import frappe
from frappe.model.document import Document


class TradexcelEmployeeBiometric(Document):
    def validate(self):
        self.biometric_id = str(self.biometric_id or "").strip()
        if not self.biometric_id:
            frappe.throw("Biometric ID / PIN is required")
        if any(char in self.biometric_id for char in ("\t", "\r", "\n")):
            frappe.throw("Biometric ID / PIN cannot contain tabs or line breaks")

        device = frappe.db.get_value(
            "Tradexcel Biometric Device", self.device,
            ["device_serial", "device_code"], as_dict=True,
        )
        if not device:
            frappe.throw("Select a valid biometric device")
        serial = str(device.device_serial or "").strip()
        if not serial:
            frappe.throw("Configure the device's real terminal serial before assigning a PIN")
        if not frappe.db.exists("Employee", self.employee):
            frappe.throw("Select a valid Employee")

        self.device_serial = serial
        self.assignment_key = hashlib.sha256(
            f"{serial}\0{self.biometric_id}".encode("utf-8")
        ).hexdigest()
        self.assigned_on = self.assigned_on or frappe.utils.today()

        existing = frappe.db.get_value(
            "Tradexcel Employee Biometric", {"assignment_key": self.assignment_key}, "name"
        )
        if existing and existing != self.name:
            frappe.throw(
                f"Biometric ID {self.biometric_id} is already assigned on device "
                f"{device.device_code or self.device} ({serial})"
            )
