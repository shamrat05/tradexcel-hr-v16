from datetime import date

from workforce_suite.workforce_suite.attendance_payroll_boundary import (
    BLOCKED,
    READY,
    REVIEW,
    attendance_period_hash,
    build_boundary_result,
    classify_employment_boundaries,
)


def test_mid_period_joiner_and_leaver_reach_native_payroll_proration():
    rows = [
        {"name": "EMP-JOIN", "date_of_joining": date(2026, 9, 10), "relieving_date": None},
        {"name": "EMP-LEAVE", "date_of_joining": date(2024, 1, 1), "relieving_date": date(2026, 9, 20)},
        {"name": "EMP-FULL", "date_of_joining": date(2024, 1, 1), "relieving_date": None},
    ]

    result = classify_employment_boundaries(rows, date(2026, 9, 1), date(2026, 9, 30))

    assert result["EMP-JOIN"]["status"] == READY
    assert result["EMP-LEAVE"]["status"] == READY
    assert result["EMP-FULL"]["status"] == READY


def test_employee_left_remains_payroll_eligible_until_inactive():
    rows = [
        {"name": "EMP-LEFT", "date_of_joining": date(2024, 1, 1),
         "relieving_date": date(2026, 9, 15), "status": "Left"},
        {"name": "EMP-INACTIVE", "date_of_joining": date(2024, 1, 1),
         "relieving_date": date(2026, 9, 15), "status": "Inactive"},
    ]

    result = classify_employment_boundaries(rows, date(2026, 9, 1), date(2026, 9, 30))

    assert result["EMP-LEFT"]["status"] == READY
    assert result["EMP-INACTIVE"]["status"] == "BLOCKED_EMPLOYMENT_STATUS"


def test_boundary_result_is_ready_only_without_blockers():
    assert build_boundary_result([])["status"] == READY
    assert build_boundary_result([{"code": "ATTENDANCE_PENDING"}])["status"] == BLOCKED
    assert build_boundary_result([{"code": "NOTICE", "severity": "review"}])["status"] == REVIEW


def test_attendance_hash_changes_when_native_state_changes():
    first = [{"employee": "EMP-1", "attendance_date": "2026-09-01", "status": "Present"}]
    second = [{"employee": "EMP-1", "attendance_date": "2026-09-01", "status": "Absent"}]

    assert attendance_period_hash(first, []) != attendance_period_hash(second, [])
    assert attendance_period_hash(first, []) == attendance_period_hash(first, [])


def test_attendance_hash_ignores_metadata_and_overtime_state():
    first = [{
        "employee": "EMP-1",
        "attendance_date": "2026-09-01",
        "status": "Present",
        "docstatus": 1,
        "modified": "2026-09-01 10:00:00",
        "notes": "before",
    }]
    edited = [{**first[0], "modified": "2026-09-20 10:00:00", "notes": "after"}]

    assert attendance_period_hash(first, [{"name": "OT-1", "total": 1}]) == attendance_period_hash(edited, [])


def test_boundary_module_is_not_allowed_to_read_raw_checkins():
    import inspect

    from workforce_suite.workforce_suite import attendance_payroll_boundary

    assert "_checkin_records" not in inspect.getsource(attendance_payroll_boundary)


def test_native_payroll_entry_dictionary_rows_are_normalized(monkeypatch):
    from workforce_suite.workforce_suite import attendance_payroll_boundary

    monkeypatch.setattr(
        attendance_payroll_boundary,
        "_employees_for_period",
        lambda *_args: [{"name": "EMP-1", "employee_name": "One", "date_of_joining": date(2024, 1, 1),
                         "relieving_date": None, "status": "Active"}],
    )
    monkeypatch.setattr(
        attendance_payroll_boundary,
        "_native_unmarked_attendance",
        lambda *_args: [{"employee": "EMP-1", "unmarked_days": 2}],
    )
    monkeypatch.setattr(attendance_payroll_boundary, "_pending_mobile_events", lambda *_args: [])
    monkeypatch.setattr(attendance_payroll_boundary, "_ambiguous_biometric_mappings", lambda *_args: [])
    monkeypatch.setattr(attendance_payroll_boundary, "_pending_attendance_requests", lambda *_args: [])
    monkeypatch.setattr(attendance_payroll_boundary, "_unapproved_overtime", lambda *_args: [])
    monkeypatch.setattr(attendance_payroll_boundary, "_unsafe_payment_day_structures", lambda *_args: [])
    monkeypatch.setattr(attendance_payroll_boundary, "_attendance_required_for_payroll", lambda: True)

    result = attendance_payroll_boundary.inspect_attendance_payroll_boundary(
        "Example Company A", date(2026, 9, 1), date(2026, 9, 30)
    )

    assert result["status"] == BLOCKED
    assert result["blockers"][0]["employee"] == "EMP-1"


def test_attendance_integrity_excludes_payroll_only_findings(monkeypatch):
    from workforce_suite.workforce_suite import attendance_payroll_boundary

    monkeypatch.setattr(
        attendance_payroll_boundary,
        "_employees_for_period",
        lambda *_args: [{"name": "EMP-JOIN", "employee_name": "Joiner", "date_of_joining": date(2026, 9, 10),
                         "relieving_date": None, "status": "Active"}],
    )
    monkeypatch.setattr(attendance_payroll_boundary, "_attendance_required_for_payroll", lambda: False)
    monkeypatch.setattr(attendance_payroll_boundary, "_attendance_required_employees", lambda *_args: [])
    monkeypatch.setattr(attendance_payroll_boundary, "_pending_mobile_events", lambda *_args: [])
    monkeypatch.setattr(attendance_payroll_boundary, "_ambiguous_biometric_mappings", lambda *_args: [])
    monkeypatch.setattr(attendance_payroll_boundary, "_pending_attendance_requests", lambda *_args: [])

    result = attendance_payroll_boundary.inspect_attendance_integrity(
        "Example Company A", date(2026, 9, 1), date(2026, 9, 30)
    )

    assert result["status"] == READY
    assert result["blockers"] == []


def test_period_fingerprint_uses_only_installed_native_attendance_fields(monkeypatch):
    from types import SimpleNamespace
    from workforce_suite.workforce_suite import attendance_payroll_boundary as boundary
    calls = []
    monkeypatch.setattr(boundary.frappe, "get_meta", lambda _: SimpleNamespace(has_field=lambda field: field not in {"branch", "department"}))
    monkeypatch.setattr(boundary.frappe, "get_all", lambda *args, **kwargs: calls.append(kwargs) or [])
    assert boundary.get_native_period_state("Synthetic Co", "2026-09-01", "2026-09-30") == []
    assert "branch" not in calls[0]["fields"] and "department" not in calls[0]["fields"]
    assert {"employee", "working_hours", "status", "docstatus"} <= set(calls[0]["fields"])


def test_optional_attendance_scope_uses_one_employee_batch_only_when_missing(monkeypatch):
    from types import SimpleNamespace
    import frappe
    from workforce_suite.workforce_suite import attendance_payroll_boundary as boundary
    calls = []
    monkeypatch.setattr(boundary.frappe, "get_meta", lambda _: SimpleNamespace(has_field=lambda field: False))
    monkeypatch.setattr(boundary.frappe, "get_all", lambda dt, **kwargs: calls.append((dt, kwargs)) or [frappe._dict(name="EMP-1", branch="Example Branch", department="Example Department")])
    rows = [frappe._dict(employee="EMP-1"), frappe._dict(employee="EMP-1")]
    assert boundary.attendance_employee_scope(rows)[0].branch == "Example Branch"
    assert len(calls) == 1 and calls[0][1]["filters"]["name"] == ["in", ["EMP-1"]]
    calls.clear()
    monkeypatch.setattr(boundary.frappe, "get_meta", lambda _: SimpleNamespace(has_field=lambda field: True))
    rows[0].branch = "Historical Snapshot"
    assert boundary.attendance_employee_scope(rows)[0].branch == "Historical Snapshot"
    assert calls == []


def test_native_overtime_approver_grant_matches_reviewed_provenance_boundary():
    from workforce_suite.role_setup import STANDARD_PERMISSION_MATRIX, READ_ONLY_PERMS
    grant = STANDARD_PERMISSION_MATRIX["Additional Salary"]["Workforce Payroll Approver"]
    assert grant == READ_ONLY_PERMS | {"create", "write", "submit"}
    assert not {"cancel", "delete", "share"} & grant
    from workforce_suite import hooks
    assert "validate_overtime_generated_additional_salary" in str(hooks.doc_events["Additional Salary"])
