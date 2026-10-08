from datetime import datetime

import pytest

from workforce_suite.workforce_suite.attendance_exceptions import (
    apply_attendance_flags,
    is_early_exit,
    is_late,
    resolve_attendance_settings,
)


EMPLOYEE = {
    "name": "E1", "company": "COMPANY_A", "branch": "Example Factory",
    "department": "Loading - COMPANY_A", "designation": "Worker",
}
SHIFT = {"start_time": "09:00:00", "end_time": "18:00:00"}


def rule(name, setting, value=None, **scope):
    base = {
        "name": name, "company": "COMPANY_A", "attendance_setting": setting,
        "attendance_value": value, "effective_from": "2026-09-01",
    }
    base.update(scope)
    return base


class Attendance:
    def __init__(self, late=1, early=0, in_time=None, out_time=None):
        self.attendance_date = "2026-09-10"
        self.late_entry = late
        self.early_exit = early
        self.in_time = in_time
        self.out_time = out_time


def test_is_late_respects_grace_minutes():
    assert is_late(SHIFT["start_time"], datetime(2026, 9, 10, 9, 20), 30) is False
    assert is_late(SHIFT["start_time"], datetime(2026, 9, 10, 9, 40), 30) is True
    assert is_late(None, datetime(2026, 9, 10, 9, 40), 30) is None


def test_is_early_exit_skips_overnight_shifts():
    assert is_early_exit(SHIFT["end_time"], datetime(2026, 9, 10, 17, 30), 15) is True
    assert is_early_exit(SHIFT["end_time"], datetime(2026, 9, 10, 17, 50), 15) is False
    assert is_early_exit("02:00:00", datetime(2026, 9, 11, 1, 0), 15) is None


def test_ignore_setting_clears_flag():
    doc = Attendance(late=1)
    assert apply_attendance_flags(doc, EMPLOYEE, [rule("r", "Ignore Late Marking")]) is True
    assert doc.late_entry == 0


def test_grace_setting_recomputes_late_flag():
    late_doc = Attendance(late=1, in_time=datetime(2026, 9, 10, 9, 20))
    apply_attendance_flags(late_doc, EMPLOYEE, [rule("r", "Late Grace Minutes", 30)], SHIFT)
    assert late_doc.late_entry == 0
    truly_late = Attendance(late=0, in_time=datetime(2026, 9, 10, 10, 0))
    apply_attendance_flags(truly_late, EMPLOYEE, [rule("r", "Late Grace Minutes", 30)], SHIFT)
    assert truly_late.late_entry == 1


def test_employee_rule_beats_department_rule():
    settings = resolve_attendance_settings(EMPLOYEE, "2026-09-10", [
        rule("dept", "Late Grace Minutes", 30, department_scope=["Loading - COMPANY_A"]),
        rule("person", "Late Grace Minutes", 60, employee="E1"),
    ])
    assert settings["Late Grace Minutes"]["name"] == "person"


def test_conflicting_same_setting_values_raise():
    with pytest.raises(ValueError, match="Conflicting"):
        resolve_attendance_settings(EMPLOYEE, "2026-09-10", [
            rule("a", "Late Grace Minutes", 30, department_scope=["Loading - COMPANY_A"]),
            rule("b", "Late Grace Minutes", 45, department_scope=["Loading - COMPANY_A"]),
        ])


def test_effective_window_filters_rules():
    assert resolve_attendance_settings(
        EMPLOYEE, "2026-08-31", [rule("r", "Ignore Late Marking")]) == {}
