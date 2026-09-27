"""Real RQ execution on an isolated test queue, using native bulk scheduling."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
import frappe
from rq import Queue
from tradex_hr.tests.persona_uat import SyntheticPersonaHarness, PERSONA_ROLES


def test_live_native_bulk_queue_revalidates_changed_scope(tmp_path):
    from frappe.utils.background_jobs import get_redis_conn

    frappe.init(
        site="hrms-v16.localhost",
        sites_path="/home/sanchita/frappe-bench-v16/sites",
        force=True,
    )
    frappe.connect()
    frappe.set_user("Administrator")
    h = SyntheticPersonaHarness("SOLQUEUE" + frappe.generate_hash(8).upper())
    queue = Queue(h.token, connection=get_redis_conn())
    jobs = []
    shift = None
    original_errors = set(frappe.get_all("Error Log", pluck="name"))
    worker = tmp_path / "worker.py"
    worker.write_text("""import sys, frappe
from rq import Queue, Worker
from frappe.utils.background_jobs import get_redis_conn
frappe.init(site="hrms-v16.localhost",force=True)
connection=get_redis_conn()
queue=Queue(sys.argv[1],connection=connection)
Worker([queue],connection=connection).work(burst=True,with_scheduler=False,logging_level="ERROR")
""")

    def execute_worker():
        with (tmp_path / "worker.log").open("a") as log:
            subprocess.run(
                [sys.executable, str(worker), queue.name],
                cwd="/home/sanchita/frappe-bench-v16/sites",
                stdout=log,
                stderr=log,
                check=True,
                timeout=120,
            )
        frappe.db.rollback()  # observe the separate worker's committed transaction

    try:
        company = "Tradexcel Ceramics Ltd."
        branches = frappe.get_all(
            "Branch", filters={"company": company}, pluck="name", order_by="name"
        )
        department = frappe.db.get_value("Department", {"company": company}, "name")
        user = h.create_user(
            "maker",
            [PERSONA_ROLES["hr_manager"]],
            company=company,
            branch=branches[0],
            department=department,
        )
        employees = [
            h.create_employee(str(i), company, branches[0], department)
            for i in range(31)
        ]
        shift = frappe.get_doc(
            {
                "doctype": "Shift Type",
                "name": h.token,
                "start_time": "08:00:00",
                "end_time": "16:00:00",
            }
        ).insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.set_user(user)
        tool = frappe.get_doc("Shift Assignment Tool")
        tool.update(
            {
                "action": "Assign Shift",
                "company": company,
                "shift_type": shift.name,
                "start_date": "2026-09-28",
                "end_date": "2026-09-28",
                "status": "Active",
            }
        )

        # Only queue destination is isolated; dispatch, serialization, worker,
        # actor hook, native processing and commit are real installed code.
        def enqueue_native():
            before = set(queue.job_ids)
            with patch("frappe.utils.background_jobs.get_queue", return_value=queue):
                tool.bulk_assign(employees)
            created = set(queue.job_ids) - before
            assert len(created) == 1
            job = queue.fetch_job(created.pop())
            jobs.append(job)
            return job

        first = enqueue_native()
        execute_worker()
        assert first.get_status(refresh=True).value == "finished"
        names = frappe.get_all(
            "Shift Assignment",
            filters={"employee": ["in", employees], "docstatus": 1},
            pluck="name",
        )
        assert len(names) == 31
        # Replay is rejected by native eligibility; no second set of assignments.
        import pytest

        with pytest.raises(frappe.PermissionError):
            tool.bulk_assign(employees)
        tool.start_date = tool.end_date = "2026-09-29"
        second = enqueue_native()
        frappe.set_user("Administrator")
        permission = frappe.get_doc(
            "User Permission",
            frappe.db.get_value(
                "User Permission", {"user": user, "allow": "Branch"}, "name"
            ),
        )
        permission.for_value = branches[1]
        permission.save(ignore_permissions=True)
        frappe.db.commit()
        execute_worker()
        assert second.get_status(refresh=True).value == "failed"
        assert (
            frappe.db.count("Shift Assignment", {"employee": ["in", employees]}) == 31
        )
        for dt in (
            "Attendance",
            "Employee Checkin",
            "Salary Structure Assignment",
            "Salary Slip",
        ):
            assert not frappe.db.exists(dt, {"employee": ["in", employees]})
    finally:
        frappe.set_user("Administrator")
        for name in (
            frappe.get_all(
                "Shift Assignment",
                filters={"employee": ["in", h.employees]},
                pluck="name",
            )
            if h.employees
            else []
        ):
            doc = frappe.get_doc("Shift Assignment", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc(
                "Shift Assignment", name, force=True, ignore_permissions=True
            )
        if shift and frappe.db.exists("Shift Type", shift.name):
            frappe.delete_doc("Shift Type", shift.name, ignore_permissions=True)
        # Dedicated worker errors contain its exact synthetic queue/job identity.
        for row in frappe.get_all("Error Log", fields=["name", "error", "method"]):
            if row.name not in original_errors and (
                h.token in (row.error or "")
                or any(e in (row.error or "") for e in h.employees)
            ):
                frappe.delete_doc("Error Log", row.name, ignore_permissions=True)
        for job in jobs:
            job.delete()
        queue.delete(delete_jobs=True)
        h.cleanup()
        frappe.destroy()
