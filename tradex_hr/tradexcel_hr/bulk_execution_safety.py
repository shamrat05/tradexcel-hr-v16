"""Actor and result-delivery boundaries around existing native bulk tools.

No jobs, selections or results are stored here. Native controllers still own
all mutations. The deferred realtime buffer is an installed-v16 compatibility
boundary, covered by a test against the real publisher and native commit flush.
"""
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.realtime import get_user_room


BULK_RESULT_EVENTS = frozenset({
    'completed_bulk_shift_assignment',
    'completed_bulk_shift_schedule_assignment',
    'completed_bulk_shift_request_processing',
    'completed_bulk_leave_allocation',
    'completed_bulk_leave_policy_assignment',
    'completed_bulk_salary_structure_assignment',
})


# Actual qualified methods emitted by installed v16 enqueue/execute_job.
ACTOR_BOUND_METHODS = frozenset({
    "tradex_hr.tradexcel_hr.shift_assignment_tool.TradexcelShiftAssignmentToolMixin._bulk_assign",
    "tradex_hr.tradexcel_hr.shift_assignment_tool.TradexcelShiftAssignmentToolMixin._bulk_process_shift_requests",
    "hrms.hr.doctype.shift_assignment_tool.shift_assignment_tool.ShiftAssignmentTool._bulk_assign",
    "hrms.hr.doctype.shift_assignment_tool.shift_assignment_tool.ShiftAssignmentTool._bulk_process_shift_requests",
    "tradex_hr.tradexcel_hr.bulk_salary_structure_assignment.TradexcelBulkSalaryStructureAssignmentMixin._bulk_prepare_drafts",
    "tradex_hr.tradexcel_hr.bulk_salary_structure_assignment.TradexcelBulkSalaryStructureAssignmentMixin._bulk_assign_structure",
    "hrms.payroll.doctype.bulk_salary_structure_assignment.bulk_salary_structure_assignment.BulkSalaryStructureAssignment._bulk_assign_structure",
    "tradex_hr.tradexcel_hr.overtime_bulk._prepare_now",
    "tradex_hr.tradexcel_hr.field_attendance_service.settle_field_duty_allowance",
    "hrms.payroll.doctype.payroll_entry.payroll_entry.create_salary_slips_for_employees",
    "hrms.payroll.doctype.payroll_entry.payroll_entry.submit_salary_slips_for_employees",
    "hrms.hr.doctype.overtime_slip.overtime_slip.create_overtime_slips_for_employees",
    "hrms.hr.doctype.overtime_slip.overtime_slip.submit_overtime_slips_for_employees",
})
ACTOR_BOUND_DOCTYPES = frozenset({
    "Employee", "Employee Checkin", "Attendance", "Attendance Request",
    "Shift Assignment Tool", "Shift Assignment", "Shift Schedule Assignment", "Shift Request",
    "Leave Control Panel", "Leave Application", "Leave Allocation", "Leave Policy Assignment",
    "Bulk Salary Structure Assignment", "Salary Structure Assignment", "Salary Structure",
    "Payroll Entry", "Salary Slip", "Additional Salary", "Overtime Slip", "Payroll Correction", "Arrear",
    "Employee Transfer", "Employee Promotion", "Employee Separation", "Full and Final Statement",
})


def _actor_bound_job(method, kwargs):
    if method in ACTOR_BOUND_METHODS:
        return True
    if method in {"frappe.utils.background_jobs.run_doc_method",
                  "frappe.desk.doctype.bulk_update.bulk_update._bulk_action",
                  "frappe.model.document.execute_action"}:
        doctype = kwargs.get("doctype") or kwargs.get("__doctype") or ""
        return doctype in ACTOR_BOUND_DOCTYPES or doctype.startswith("Tradexcel ")
    if method == "frappe.core.doctype.data_import.data_import.start_import":
        doctype = frappe.db.get_value("Data Import", kwargs.get("data_import"), "reference_doctype") or ""
        return doctype in ACTOR_BOUND_DOCTYPES or doctype.startswith("Tradexcel ")
    return False


def validate_job_actor(method=None, kwargs=None, transaction_type=None):
    """Fail closed only for actor-bound HR mutations, never unrelated retries."""
    job = getattr(frappe.local, 'job', None)
    job_method = job.get('method') if job else method
    job_kwargs = (job.get('kwargs') if job else None) or kwargs or {}
    if not (_actor_bound_job(job_method, job_kwargs) or _actor_bound_job(method, kwargs or job_kwargs)):
        return
    actor = job.get('user') if job else None
    if actor in (None, '', 'Guest') or (method and job_method and method != job_method) or actor != frappe.session.user or not frappe.db.get_value('User', actor, 'enabled'):
        frappe.throw(
            _('This queued work has lost its original user or that user is disabled. Review and retry it from the original workflow.'),
            frappe.PermissionError,
        )


@contextmanager
def private_bulk_results():
    """Readdress only this native call's deferred messages before they can flush."""
    actor = frappe.session.user
    if not actor or actor == 'Guest' or not frappe.db.get_value('User', actor, 'enabled'):
        frappe.throw(_('Sign in with an enabled operator account to use this tool.'), frappe.PermissionError)
    start = len(getattr(frappe.local, '_realtime_log', []))
    try:
        yield
        if actor != frappe.session.user or not frappe.db.get_value('User', actor, 'enabled'):
            frappe.throw(_('The operator changed before completion. Refresh and retry.'), frappe.PermissionError)
        pending = getattr(frappe.local, '_realtime_log', [])
        if not isinstance(pending, list) or any(not isinstance(row, (list, tuple)) or len(row) != 3 for row in pending):
            frappe.throw(_('Bulk result delivery needs a compatibility review before this operation can complete.'))
        # Installed controllers defer these messages and never commit inside their
        # loops. Scope before returning to HTTP/job commit, retaining native flush.
        for index in range(start, len(pending)):
            event, message, room = pending[index]
            if event in BULK_RESULT_EVENTS:
                pending[index] = [event, message, get_user_room(actor)]
    except BaseException:
        # A caller may catch the failure and commit unrelated work. Never leave
        # this failed call's deferred completion payloads in a public room.
        pending = getattr(frappe.local, '_realtime_log', [])
        if isinstance(pending, list):
            del pending[start:]
        raise
