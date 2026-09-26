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


def validate_job_actor(method=None, kwargs=None, transaction_type=None):
    """A native retry must never replace its submitter with Administrator."""
    job = getattr(frappe.local, 'job', None)
    actor = job.get('user') if job else None
    if not actor or actor != frappe.session.user or not frappe.db.get_value('User', actor, 'enabled'):
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
