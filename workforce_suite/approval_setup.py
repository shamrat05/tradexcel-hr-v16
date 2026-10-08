"""Approval workflows for controlled Workforce Suite operations."""

from __future__ import annotations

from collections.abc import Iterable

import frappe


WORKFLOWS = {
    "Workforce Statutory Rule Set Approval": {
        "document_type": "Workforce Statutory Rule Set",
        "states": (
            ("Workforce Statutory Draft", "0", "Workforce Suite Manager"),
            ("Workforce Statutory Pending Approval", "0", "Workforce Owner/Director"),
            ("Workforce Statutory Approved", "1", "Workforce Compliance Auditor"),
            ("Workforce Statutory Rejected", "0", "Workforce Suite Manager"),
        ),
        "transitions": (
            ("Workforce Statutory Draft", "Submit for Legal Review", "Workforce Statutory Pending Approval", "Workforce Suite Manager", None, 1),
            ("Workforce Statutory Pending Approval", "Approve Rule Set", "Workforce Statutory Approved", "Workforce Owner/Director"),
            ("Workforce Statutory Pending Approval", "Reject Rule Set", "Workforce Statutory Rejected", "Workforce Owner/Director"),
            ("Workforce Statutory Rejected", "Return to Draft", "Workforce Statutory Draft", "Workforce Suite Manager"),
        ),
    },
    "Workforce Attendance Correction": {
        "document_type": "Attendance Request",
        "states": (
            ("Workforce Attendance Draft", "0", "Workforce Employee/Worker"),
            ("Workforce Attendance Pending Approval", "0", "Workforce Attendance Correction Approver"),
            ("Workforce Attendance Approved", "1", "Workforce Attendance Correction Approver"),
            ("Workforce Attendance Rejected", "0", "Workforce Attendance Correction Approver"),
            ("Workforce Attendance Cancelled", "2", "Workforce Suite Manager"),
        ),
        "transitions": (
            ("Workforce Attendance Draft", "Send for Approval", "Workforce Attendance Pending Approval", "Workforce Employee/Worker"),
            ("Workforce Attendance Pending Approval", "Approve", "Workforce Attendance Approved", "Workforce Attendance Correction Approver"),
            ("Workforce Attendance Pending Approval", "Reject", "Workforce Attendance Rejected", "Workforce Attendance Correction Approver"),
            ("Workforce Attendance Approved", "Cancel", "Workforce Attendance Cancelled", "Workforce Suite Manager"),
        ),
    },
    "Workforce Leave Approval": {
        "document_type": "Leave Application",
        "states": (
            ("Workforce Leave Draft", "0", "Workforce Employee/Worker"),
            ("Workforce Leave Pending Approval", "0", "Workforce Leave Approver"),
            ("Workforce Leave Pending HR Review", "0", "Workforce Suite Manager"),
            ("Workforce Leave Approved", "1", "Workforce Suite Manager"),
            ("Workforce Leave Rejected", "0", "Workforce Leave Approver"),
            ("Workforce Leave Cancelled", "2", "Workforce Suite Manager"),
        ),
        "transitions": (
            ("Workforce Leave Draft", "Send for Approval", "Workforce Leave Pending Approval", "Workforce Employee/Worker"),
            ("Workforce Leave Pending Approval", "Manager Approve", "Workforce Leave Pending HR Review", "Workforce Leave Approver"),
            ("Workforce Leave Pending Approval", "Reject", "Workforce Leave Rejected", "Workforce Leave Approver"),
            ("Workforce Leave Pending HR Review", "Approve", "Workforce Leave Approved", "Workforce Suite Manager"),
            ("Workforce Leave Pending HR Review", "Reject", "Workforce Leave Rejected", "Workforce Suite Manager"),
            ("Workforce Leave Approved", "Cancel", "Workforce Leave Cancelled", "Workforce Suite Manager"),
        ),
    },
    "Workforce Payroll Approval": {
        "document_type": "Payroll Entry",
        "states": (
            ("Workforce Payroll Draft", "0", "Workforce Payroll Manager"),
            ("Workforce Payroll Pending Review", "1", "Workforce Payroll Approver"),
            ("Workforce Payroll Pending Director Approval", "1", "Workforce Owner/Director"),
            ("Workforce Payroll Approved", "1", "Workforce Owner/Director"),
            ("Workforce Payroll Rejected", "2", "Workforce Payroll Approver"),
            ("Workforce Payroll Cancelled", "2", "Workforce Owner/Director"),
        ),
        "transitions": (
            ("Workforce Payroll Draft", "Submit for Review", "Workforce Payroll Pending Review", "Workforce Payroll Manager", None, 1),
            ("Workforce Payroll Pending Review", "Review Complete", "Workforce Payroll Pending Director Approval", "Workforce Payroll Approver", 'doc.salary_slips_created and doc.status not in ("Queued", "Failed")'),
            ("Workforce Payroll Pending Review", "Reject", "Workforce Payroll Rejected", "Workforce Payroll Approver", 'doc.status != "Queued"'),
            ("Workforce Payroll Pending Director Approval", "Approve", "Workforce Payroll Approved", "Workforce Owner/Director", 'doc.salary_slips_created and doc.status not in ("Queued", "Failed")'),
            ("Workforce Payroll Pending Director Approval", "Reject", "Workforce Payroll Rejected", "Workforce Owner/Director", 'doc.status != "Queued"'),
            ("Workforce Payroll Approved", "Cancel", "Workforce Payroll Cancelled", "Workforce Owner/Director"),
        ),
    },
    "Workforce Payroll Correction Approval": {
        "document_type": "Payroll Correction",
        "states": (
            ("Workforce Adjustment Draft", "0", "All"),
            ("Workforce Adjustment Pending Approval", "0", "All"),
            ("Workforce Adjustment Approved", "1", "Workforce Payroll Approver"),
            ("Workforce Adjustment Rejected", "0", "All"),
            ("Workforce Adjustment Cancelled", "2", "Workforce Owner/Director"),
        ),
        "transitions": (
            ("Workforce Adjustment Draft", "Submit for Approval", "Workforce Adjustment Pending Approval", "Workforce Payroll Manager", None, 1),
            ("Workforce Adjustment Draft", "Submit for Approval", "Workforce Adjustment Pending Approval", "Workforce Suite Manager", None, 1),
            ("Workforce Adjustment Pending Approval", "Approve", "Workforce Adjustment Approved", "Workforce Payroll Approver"),
            ("Workforce Adjustment Pending Approval", "Reject", "Workforce Adjustment Rejected", "Workforce Payroll Approver"),
            ("Workforce Adjustment Rejected", "Return to Draft", "Workforce Adjustment Draft", "Workforce Payroll Manager"),
            ("Workforce Adjustment Rejected", "Return to Draft", "Workforce Adjustment Draft", "Workforce Suite Manager"),
            ("Workforce Adjustment Approved", "Cancel", "Workforce Adjustment Cancelled", "Workforce Owner/Director"),
        ),
    },
    "Workforce Full & Final Approval": {
        "document_type": "Full and Final Statement",
        "states": (
            ("Workforce F&F Draft", "0", "Workforce Suite Manager"),
            ("Workforce F&F Pending Finance", "0", "Workforce Finance/Accounts Officer"),
            ("Workforce F&F Approved", "1", "Workforce Finance/Accounts Officer"),
            ("Workforce F&F Rejected", "0", "Workforce Finance/Accounts Officer"),
            ("Workforce F&F Cancelled", "2", "Workforce Finance/Accounts Officer"),
        ),
        "transitions": (
            ("Workforce F&F Draft", "Submit for Finance Review", "Workforce F&F Pending Finance", "Workforce Suite Manager", None, 1),
            ("Workforce F&F Pending Finance", "Approve and Submit", "Workforce F&F Approved", "Workforce Finance/Accounts Officer"),
            ("Workforce F&F Pending Finance", "Reject", "Workforce F&F Rejected", "Workforce Finance/Accounts Officer"),
            ("Workforce F&F Rejected", "Return to Draft", "Workforce F&F Draft", "Workforce Suite Manager"),
            ("Workforce F&F Approved", "Cancel", "Workforce F&F Cancelled", "Workforce Finance/Accounts Officer"),
        ),
    },
    "Workforce Arrear Approval": {
        "document_type": "Arrear",
        "states": (
            ("Workforce Adjustment Draft", "0", "All"),
            ("Workforce Adjustment Pending Approval", "0", "All"),
            ("Workforce Adjustment Approved", "1", "Workforce Payroll Approver"),
            ("Workforce Adjustment Rejected", "0", "All"),
            ("Workforce Adjustment Cancelled", "2", "Workforce Owner/Director"),
        ),
        "transitions": (
            ("Workforce Adjustment Draft", "Submit for Approval", "Workforce Adjustment Pending Approval", "Workforce Payroll Manager", None, 1),
            ("Workforce Adjustment Draft", "Submit for Approval", "Workforce Adjustment Pending Approval", "Workforce Suite Manager", None, 1),
            ("Workforce Adjustment Pending Approval", "Approve", "Workforce Adjustment Approved", "Workforce Payroll Approver"),
            ("Workforce Adjustment Pending Approval", "Reject", "Workforce Adjustment Rejected", "Workforce Payroll Approver"),
            ("Workforce Adjustment Rejected", "Return to Draft", "Workforce Adjustment Draft", "Workforce Payroll Manager"),
            ("Workforce Adjustment Rejected", "Return to Draft", "Workforce Adjustment Draft", "Workforce Suite Manager"),
            ("Workforce Adjustment Approved", "Cancel", "Workforce Adjustment Cancelled", "Workforce Owner/Director"),
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


def ensure_workforce_workflows() -> dict[str, int]:
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
