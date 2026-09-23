"""Approval workflows for controlled Tradexcel HR operations."""

from __future__ import annotations

from collections.abc import Iterable

import frappe


WORKFLOWS = {
    "Tradexcel Attendance Correction": {
        "document_type": "Attendance Request",
        "states": (
            ("Tradexcel Attendance Draft", "0", "Tradexcel Employee/Worker"),
            ("Tradexcel Attendance Pending Approval", "0", "Tradexcel Attendance Correction Approver"),
            ("Tradexcel Attendance Approved", "1", "Tradexcel Attendance Correction Approver"),
            ("Tradexcel Attendance Rejected", "0", "Tradexcel Attendance Correction Approver"),
            ("Tradexcel Attendance Cancelled", "2", "Tradexcel HR Manager"),
        ),
        "transitions": (
            ("Tradexcel Attendance Draft", "Send for Approval", "Tradexcel Attendance Pending Approval", "Tradexcel Employee/Worker"),
            ("Tradexcel Attendance Pending Approval", "Approve", "Tradexcel Attendance Approved", "Tradexcel Attendance Correction Approver"),
            ("Tradexcel Attendance Pending Approval", "Reject", "Tradexcel Attendance Rejected", "Tradexcel Attendance Correction Approver"),
            ("Tradexcel Attendance Approved", "Cancel", "Tradexcel Attendance Cancelled", "Tradexcel HR Manager"),
        ),
    },
    "Tradexcel Leave Approval": {
        "document_type": "Leave Application",
        "states": (
            ("Tradexcel Leave Draft", "0", "Tradexcel Employee/Worker"),
            ("Tradexcel Leave Pending Approval", "0", "Tradexcel Leave Approver"),
            ("Tradexcel Leave Pending HR Review", "0", "Tradexcel HR Manager"),
            ("Tradexcel Leave Approved", "1", "Tradexcel HR Manager"),
            ("Tradexcel Leave Rejected", "0", "Tradexcel Leave Approver"),
            ("Tradexcel Leave Cancelled", "2", "Tradexcel HR Manager"),
        ),
        "transitions": (
            ("Tradexcel Leave Draft", "Send for Approval", "Tradexcel Leave Pending Approval", "Tradexcel Employee/Worker"),
            ("Tradexcel Leave Pending Approval", "Manager Approve", "Tradexcel Leave Pending HR Review", "Tradexcel Leave Approver"),
            ("Tradexcel Leave Pending Approval", "Reject", "Tradexcel Leave Rejected", "Tradexcel Leave Approver"),
            ("Tradexcel Leave Pending HR Review", "Approve", "Tradexcel Leave Approved", "Tradexcel HR Manager"),
            ("Tradexcel Leave Pending HR Review", "Reject", "Tradexcel Leave Rejected", "Tradexcel HR Manager"),
            ("Tradexcel Leave Approved", "Cancel", "Tradexcel Leave Cancelled", "Tradexcel HR Manager"),
        ),
    },
    "Tradexcel Payroll Approval": {
        "document_type": "Payroll Entry",
        "states": (
            ("Tradexcel Payroll Draft", "0", "Tradexcel Payroll Manager"),
            ("Tradexcel Payroll Pending Review", "1", "Tradexcel Payroll Approver"),
            ("Tradexcel Payroll Pending Director Approval", "1", "Tradexcel Owner/Director"),
            ("Tradexcel Payroll Approved", "1", "Tradexcel Owner/Director"),
            ("Tradexcel Payroll Rejected", "2", "Tradexcel Payroll Approver"),
            ("Tradexcel Payroll Cancelled", "2", "Tradexcel Owner/Director"),
        ),
        "transitions": (
            ("Tradexcel Payroll Draft", "Submit for Review", "Tradexcel Payroll Pending Review", "Tradexcel Payroll Manager", None, 1),
            ("Tradexcel Payroll Pending Review", "Review Complete", "Tradexcel Payroll Pending Director Approval", "Tradexcel Payroll Approver", 'doc.salary_slips_created and doc.status not in ("Queued", "Failed")'),
            ("Tradexcel Payroll Pending Review", "Reject", "Tradexcel Payroll Rejected", "Tradexcel Payroll Approver", 'doc.status != "Queued"'),
            ("Tradexcel Payroll Pending Director Approval", "Approve", "Tradexcel Payroll Approved", "Tradexcel Owner/Director", 'doc.salary_slips_created and doc.status not in ("Queued", "Failed")'),
            ("Tradexcel Payroll Pending Director Approval", "Reject", "Tradexcel Payroll Rejected", "Tradexcel Owner/Director", 'doc.status != "Queued"'),
            ("Tradexcel Payroll Approved", "Cancel", "Tradexcel Payroll Cancelled", "Tradexcel Owner/Director"),
        ),
    },
}


def _ensure_state(state_name: str) -> None:
    if frappe.db.exists("Workflow State", state_name):
        return
    frappe.get_doc({
        "doctype": "Workflow State",
        "workflow_state_name": state_name,
        "style": "Info",
    }).insert(ignore_permissions=True)


def _ensure_action(action_name: str) -> None:
    if frappe.db.exists("Workflow Action Master", action_name):
        return
    frappe.get_doc({
        "doctype": "Workflow Action Master",
        "workflow_action_name": action_name,
    }).insert(ignore_permissions=True)


def _replace_rows(doc, fieldname: str, rows: Iterable[dict]) -> None:
    setattr(doc, fieldname, [])
    for row in rows:
        doc.append(fieldname, row)


def _transition_row(transition: tuple) -> dict:
    state, action, next_state, allowed, *options = transition
    condition = options[0] if options else None
    allow_self_approval = options[1] if len(options) > 1 else 0
    row = {
        "state": state,
        "action": action,
        "next_state": next_state,
        "allowed": allowed,
        "allow_self_approval": allow_self_approval,
    }
    if condition:
        row["condition"] = condition
    return row


def ensure_tradex_workflows() -> dict[str, int]:
    """Create or converge the four-eyes approval workflows idempotently."""
    created_or_updated = 0
    for workflow_name, definition in WORKFLOWS.items():
        if not frappe.db.exists("DocType", definition["document_type"]):
            continue
        for state_name, _doc_status, _allow_edit in definition["states"]:
            _ensure_state(state_name)
        for transition in definition["transitions"]:
            _ensure_action(transition[1])

        if frappe.db.exists("Workflow", workflow_name):
            workflow = frappe.get_doc("Workflow", workflow_name)
        else:
            workflow = frappe.get_doc({
                "doctype": "Workflow",
                "workflow_name": workflow_name,
            })
        workflow.document_type = definition["document_type"]
        workflow.is_active = 1
        workflow.override_status = 0
        workflow.send_email_alert = 0
        workflow.workflow_state_field = "workflow_state"
        _replace_rows(
            workflow,
            "states",
            (
                {
                    "state": state_name,
                    "doc_status": doc_status,
                    "allow_edit": allow_edit,
                }
                for state_name, doc_status, allow_edit in definition["states"]
            ),
        )
        _replace_rows(
            workflow,
            "transitions",
            (_transition_row(transition) for transition in definition["transitions"]),
        )
        workflow.save(ignore_permissions=True)
        created_or_updated += 1

    frappe.clear_cache()
    return {"workflows_created_or_updated": created_or_updated}
