from pathlib import Path


REPORT_ROOT = Path(__file__).resolve().parents[1] / "tradexcel_hr" / "report"
REPORTS = (
    "daily_attendance_summary",
    "tradexcel_daily_attendance_board",
    "tradexcel_payroll_register",
    "tradexcel_salary_coverage_board",
    "tradexcel_leave_balance_board",
    "employee_data_gaps",
    "workforce_anomaly_radar",
)


def test_tradexcel_reports_have_print_templates():
    for report in REPORTS:
        template = (REPORT_ROOT / report / f"{report}.html").read_text(encoding="utf-8")

        assert "report.get_columns_for_print()" in template
        assert "Printed On" in template
        assert "No records found" in template


def test_salary_coverage_report_has_a_module():
    report = REPORT_ROOT / "tradexcel_salary_coverage_board" / "tradexcel_salary_coverage_board.py"

    assert report.exists()
    source = report.read_text(encoding="utf-8")
    assert "def execute" in source
    assert "assignment_status" in source
    assert "structure_company" in source
    assert "salary_basis" in source
    assert "resolve_pay_basis" in source
    assert "MONTHLY" in source and "DAILY" in source
    assert "Pay Basis Missing" in source
    assert "e.employment_type" not in source
    assert "TCL Factory Daily Wage Worker Structure" not in source
    assert "Selevo Source Salary" not in source
