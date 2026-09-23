from tradex_hr.role_setup import STANDARD_PERMISSION_MATRIX


def test_employee_self_service_role_is_not_broad_employee_directory_access():
    assert "read" not in STANDARD_PERMISSION_MATRIX["Employee"]["Tradexcel Employee/Worker"]


def test_payroll_preparer_can_use_native_batch_but_individual_slips_are_guarded():
    # HRMS calls SalarySlip.submit() from PayrollEntry.submit_salary_slips().
    # The native right is granted to the Payroll Manager, while the server-side
    # managed-slip hook permits submission only with via_payroll_entry=True.
    assert "submit" in STANDARD_PERMISSION_MATRIX["Salary Slip"]["Tradexcel Payroll Manager"]
    assert "submit" not in STANDARD_PERMISSION_MATRIX["Salary Slip"]["Tradexcel Payroll Approver"]


def test_payroll_approver_cannot_submit_salary_slips_independently():
    approver = STANDARD_PERMISSION_MATRIX["Salary Slip"]["Tradexcel Payroll Approver"]
    assert "submit" not in approver
    assert "submit" in STANDARD_PERMISSION_MATRIX["Payroll Entry"]["Tradexcel Payroll Approver"]
