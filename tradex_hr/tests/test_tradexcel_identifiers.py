from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
OLD_IDENTIFIERS = (
    "Tradex HR",
    "Tradex Biometric Device",
    "Tradex Employee Biometric",
    "Tradex Payroll Policy",
    "Tradex Owner/Director",
    "Tradex HR Manager",
    "Tradex HR/Attendance Officer",
    "Tradex Payroll Manager",
    "Tradex Finance/Accounts Officer",
    "Tradex Factory Supervisor",
    "Tradex Branch Manager",
    "Tradex Department Manager",
    "Tradex Device/IT Administrator",
    "Tradex Compliance Auditor",
    "Tradex Employee/Worker",
    "Tradex Attendance Correction Approver",
    "Tradex Leave Approver",
    "Tradex Payroll Approver",
    "Tradex Import Reviewer",
)


def test_custom_frappe_identifiers_use_tradexcel_brand():
    assert (APP_ROOT / "tradex_hr" / "modules.txt").read_text(encoding="utf-8").strip() == "Tradexcel HR"
    assert (APP_ROOT / "tradex_hr" / "tradexcel_hr" / "doctype" / "tradexcel_biometric_device" / "tradexcel_biometric_device.json").exists()
    assert (APP_ROOT / "tradex_hr" / "tradexcel_hr" / "doctype" / "tradexcel_employee_biometric" / "tradexcel_employee_biometric.json").exists()
    assert (APP_ROOT / "tradex_hr" / "tradexcel_hr" / "doctype" / "tradexcel_payroll_policy" / "tradexcel_payroll_policy.json").exists()

    for path in APP_ROOT.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or "archive" in path.parts:
            continue
        # This file necessarily contains the forbidden strings as its fixture;
        # scanning itself would always fail. (It only passed while it lived in
        # sync/, outside the scanned tree.)
        if path.resolve() == Path(__file__).resolve():
            continue
        if path.suffix not in {".py", ".json", ".js", ".txt", ".md", ".toml"}:
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(identifier in source for identifier in OLD_IDENTIFIERS), path
