from tradex_hr.role_setup import STANDARD_PERMISSION_MATRIX


def test_employee_self_service_role_is_not_broad_employee_directory_access():
    assert "read" not in STANDARD_PERMISSION_MATRIX["Employee"]["Tradexcel Employee/Worker"]


def test_payroll_preparer_cannot_submit_salary_slip():
    assert "submit" not in STANDARD_PERMISSION_MATRIX["Salary Slip"]["Tradexcel Payroll Manager"]
    assert "submit" in STANDARD_PERMISSION_MATRIX["Salary Slip"]["Tradexcel Payroll Approver"]
