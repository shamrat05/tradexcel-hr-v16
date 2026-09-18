"""Frappe-side controls for the SenseFace bridge.

The terminal still requires its own Cloud Server Settings to be saved. These
methods push the same profile to the bridge and make that state editable and
auditable from the Frappe Desk.
"""

from __future__ import annotations

import hashlib
from urllib.parse import quote, urlparse

import frappe
import requests


LOCAL_BRIDGE_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _require_post():
    request = getattr(frappe, "request", None)
    if request and getattr(request, "method", "POST") != "POST":
        raise frappe.PermissionError("This device action requires POST")


def _require_permission(doc, ptype: str):
    doc.check_permission(ptype)


def _bridge_url(value: str) -> str:
    parsed = urlparse(str(value or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise frappe.ValidationError("Bridge URL must be an absolute http:// or https:// URL")
    if parsed.username or parsed.password or ".." in parsed.path:
        raise frappe.ValidationError("Bridge URL contains unsupported path or credentials")
    hostname = (parsed.hostname or "").rstrip(".").lower()
    allowed = frappe.conf.get("tradex_allowed_bridge_hosts") or []
    if isinstance(allowed, str):
        allowed = [item.strip() for item in allowed.split(",") if item.strip()]
    allowed = LOCAL_BRIDGE_HOSTS | {str(item).rstrip(".").lower() for item in allowed}
    if hostname not in allowed:
        raise frappe.ValidationError(
            "Bridge host is not allowlisted. Add the exact HTTPS host to "
            "tradex_allowed_bridge_hosts in site configuration."
        )
    if hostname not in LOCAL_BRIDGE_HOSTS and parsed.scheme != "https":
        raise frappe.ValidationError("A non-local bridge must use HTTPS")
    return str(value).rstrip("/")


def _api_key(doc) -> str:
    return doc.get_password("bridge_api_key") or ""


def _payload(doc) -> dict:
    bridge = urlparse(_bridge_url(doc.bridge_url))
    return {
        "server_address": doc.server_address or bridge.hostname,
        "server_port": int(doc.server_port or (443 if doc.enable_https else 8090)),
        "enable_https": bool(doc.enable_https),
        "enable_domain_name": bool(doc.enable_domain_name),
        "api_path": doc.api_path or "/iclock",
    }


@frappe.whitelist()
def push_device_configuration(device_name: str) -> dict:
    _require_post()
    doc = frappe.get_doc("Tradexcel Biometric Device", device_name)
    _require_permission(doc, "write")
    bridge_url = _bridge_url(doc.bridge_url)
    headers = {"Accept": "application/json"}
    api_key = _api_key(doc)
    if api_key:
        headers["X-API-Key"] = api_key
    try:
        response = requests.post(
            f"{bridge_url}/api/v1/devices/{quote(doc.device_serial, safe='')}/configure",
            json=_payload(doc), headers=headers, timeout=(5, 20), allow_redirects=False,
        )
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError) as exc:
        doc.db_set({"last_sync_status": "Error", "last_sync_error": str(exc)[:500]}, update_modified=False)
        raise frappe.ValidationError(f"Bridge configuration failed: {exc}") from exc
    status = "Warning" if (
        isinstance(result, dict)
        and result.get("terminal_configuration_status") == "manual_required"
    ) else "Healthy"
    doc.db_set({"last_sync_status": status, "last_sync_error": ""}, update_modified=False)
    return result


@frappe.whitelist()
def check_device_bridge(device_name: str) -> dict:
    _require_post()
    doc = frappe.get_doc("Tradexcel Biometric Device", device_name)
    _require_permission(doc, "write")
    bridge_url = _bridge_url(doc.bridge_url)
    headers = {"Accept": "application/json"}
    api_key = _api_key(doc)
    if api_key:
        headers["X-API-Key"] = api_key
    try:
        response = requests.get(
            f"{bridge_url}/health", headers=headers, timeout=(5, 15), allow_redirects=False
        )
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError) as exc:
        doc.db_set({"last_sync_status": "Error", "last_sync_error": str(exc)[:500]}, update_modified=False)
        raise frappe.ValidationError(f"Bridge health check failed: {exc}") from exc
    doc.db_set({"last_sync_status": "Healthy", "last_seen": frappe.utils.now_datetime(),
                "last_sync_error": ""}, update_modified=False)
    return result


@frappe.whitelist()
def assign_employee_biometric(
    employee: str, device: str, biometric_id: str,
    source: str = "Manual", source_reference: str = "",
) -> dict:
    """Assign a PIN to one terminal without allowing same-device ownership conflicts."""
    _require_post()
    employee_name = str(employee or "").strip()
    device_name = str(device or "").strip()
    pin = str(biometric_id or "").strip()
    if not employee_name:
        raise frappe.ValidationError("Employee is required")
    if not device_name:
        raise frappe.ValidationError("Device is required")
    if not pin:
        raise frappe.ValidationError("Biometric ID is required")
    if any(char in pin for char in ("\t", "\r", "\n")):
        raise frappe.ValidationError("Biometric ID cannot contain tabs or line breaks")
    if source not in {"Manual", "Selevo Import", "Bridge Transfer", "Bulk Assignment"}:
        raise frappe.ValidationError("Unsupported biometric assignment source")

    employee_doc = frappe.get_doc("Employee", employee_name)
    employee_doc.check_permission("read")
    device_doc = frappe.get_doc("Tradexcel Biometric Device", device_name)
    device_doc.check_permission("read")
    if not str(device_doc.device_serial or "").strip():
        raise frappe.ValidationError(
            "Enter the real terminal serial on the device before assigning a PIN"
        )

    existing = frappe.db.get_value(
        "Tradexcel Employee Biometric",
        {"device": device_name, "biometric_id": pin},
        ["name", "employee"],
        as_dict=True,
    )
    if existing and existing.employee != employee_name:
        raise frappe.ValidationError(
            f"Biometric ID {pin} is already assigned on {device_doc.device_code} "
            f"to {existing.employee}"
        )
    if existing:
        if not frappe.has_permission("Tradexcel Employee Biometric", "write", existing.name):
            raise frappe.PermissionError("You cannot change this biometric assignment")
        frappe.db.set_value(
            "Tradexcel Employee Biometric", existing.name,
            {"enabled": 1, "enrollment_status": "Pending"},
            update_modified=True,
        )
        assignment_name = existing.name
    else:
        if not frappe.has_permission("Tradexcel Employee Biometric", "create"):
            raise frappe.PermissionError("You cannot create biometric assignments")
        assignment = frappe.get_doc({
            "doctype": "Tradexcel Employee Biometric",
            "employee": employee_name,
            "device": device_name,
            "biometric_id": pin,
            "enabled": 1,
            "enrollment_status": "Pending",
            "source": source,
            "source_reference": str(source_reference or "")[:140],
        })
        assignment.insert()
        assignment_name = assignment.name

    return {
        "assignment": assignment_name,
        "employee": employee_doc.name,
        "employee_name": employee_doc.employee_name,
        "device": device_doc.name,
        "device_code": device_doc.device_code,
        "device_serial": device_doc.device_serial,
        "biometric_id": pin,
    }


@frappe.whitelist()
def transfer_employee_biometric(
    employee: str, source_device: str, target_device: str,
    target_biometric_id: str = "", dry_run: int | bool = 0,
    confirm_transfer: int | bool = 0,
) -> dict:
    """Queue a safe template copy through the central bridge.

    Frappe records the target PIN only after the bridge accepts the job. Raw
    face/fingerprint templates never pass through the browser or Frappe DB.
    """
    _require_post()
    employee_name = str(employee or "").strip()
    source_name = str(source_device or "").strip()
    target_name = str(target_device or "").strip()
    if not employee_name or not source_name or not target_name:
        raise frappe.ValidationError("Employee, source device, and target device are required")
    if source_name == target_name:
        raise frappe.ValidationError("Source and target devices must be different")

    employee_doc = frappe.get_doc("Employee", employee_name)
    employee_doc.check_permission("read")
    source_doc = frappe.get_doc("Tradexcel Biometric Device", source_name)
    target_doc = frappe.get_doc("Tradexcel Biometric Device", target_name)
    source_doc.check_permission("read")
    target_doc.check_permission("write")
    source_serial = str(source_doc.device_serial or "").strip()
    target_serial = str(target_doc.device_serial or "").strip()
    if not source_serial or not target_serial:
        raise frappe.ValidationError("Both devices need their real terminal serial before transfer")
    if _bridge_url(source_doc.bridge_url) != _bridge_url(target_doc.bridge_url):
        raise frappe.ValidationError("Source and target devices must use the same central bridge")

    source_assignment = frappe.db.get_value(
        "Tradexcel Employee Biometric",
        {"employee": employee_name, "device": source_name, "enabled": 1},
        ["biometric_id"], as_dict=True,
    )
    if not source_assignment:
        raise frappe.ValidationError("The Employee has no enabled PIN assignment on the source device")
    source_pin = str(source_assignment.biometric_id).strip()
    target_pin = str(target_biometric_id or source_pin).strip()
    if not target_pin or any(char in target_pin for char in ("\t", "\r", "\n")):
        raise frappe.ValidationError("Target biometric ID is invalid")
    existing_target = frappe.db.get_value(
        "Tradexcel Employee Biometric",
        {"device": target_name, "biometric_id": target_pin},
        ["employee"], as_dict=True,
    )
    if existing_target and existing_target.employee != employee_name:
        raise frappe.ValidationError("That target PIN is already assigned to another Employee in Frappe")

    bridge_url = _bridge_url(target_doc.bridge_url)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    api_key = _api_key(target_doc)
    if api_key:
        headers["X-API-Key"] = api_key
    request_key = "tradex-biometric-transfer-v1:" + hashlib.sha256(
        f"{employee_name}\0{source_name}\0{target_name}\0{target_pin}".encode("utf-8")
    ).hexdigest()
    payload = {
        "source_serial": source_serial,
        "target_serial": target_serial,
        "employee_ids": [source_pin],
        "pin_map": {source_pin: target_pin},
        "dry_run": bool(dry_run),
        "confirm_transfer": bool(confirm_transfer),
    }
    try:
        response = requests.post(
            f"{bridge_url}/api/v1/device-transfers", json=payload,
            headers={**headers, "Idempotency-Key": request_key}, timeout=(5, 30),
        )
        result = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise frappe.ValidationError(f"Biometric transfer failed: {exc}") from exc
    if response.status_code >= 400:
        message = result.get("message") or result.get("error") if isinstance(result, dict) else "bridge rejected the transfer"
        raise frappe.ValidationError(f"Biometric transfer rejected: {message}")
    if not isinstance(result, dict):
        raise frappe.ValidationError("Bridge returned an invalid transfer response")
    if bool(dry_run):
        return result

    assignment_result = assign_employee_biometric(
        employee_name, target_name, target_pin,
        source="Bridge Transfer", source_reference=str(result.get("transfer_id") or ""),
    )
    result["target_assignment"] = assignment_result
    return result


@frappe.whitelist()
def assign_biometric_id(employee: str, biometric_id: str) -> dict:
    """Backward-compatible wrapper for installations with one active device.

    Multi-device installations must use ``assign_employee_biometric`` so a
    global Employee PIN can never be mistaken for a terminal assignment.
    """
    _require_post()
    devices = frappe.get_all(
        "Tradexcel Biometric Device",
        filters={"enabled": 1},
        fields=["name", "device_code", "device_serial"],
        limit_page_length=0,
    )
    configured = [row for row in devices if str(row.device_serial or "").strip()]
    if len(configured) != 1:
        raise frappe.ValidationError(
            "Select a device. Device-specific assignment is required when more than one "
            "terminal exists."
        )
    return assign_employee_biometric(employee, configured[0].name, biometric_id)
