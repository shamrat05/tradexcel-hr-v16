from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
OLD_IDENTIFIERS = (
    "Workforce Suite",
    "Workforce Biometric Device",
    "Workforce Employee Biometric",
    "Workforce Payroll Policy",
    "Workforce Owner/Director",
    "Workforce Suite Manager",
    "Workforce Suite/Attendance Officer",
    "Workforce Payroll Manager",
    "Workforce Finance/Accounts Officer",
    "Workforce Factory Supervisor",
    "Workforce Branch Manager",
    "Workforce Department Manager",
    "Workforce Device/IT Administrator",
    "Workforce Compliance Auditor",
    "Workforce Employee/Worker",
    "Workforce Attendance Correction Approver",
    "Workforce Leave Approver",
    "Workforce Payroll Approver",
    "Workforce Import Reviewer",
)


def test_custom_frappe_identifiers_use_workforce_brand():
    assert (APP_ROOT / "workforce_suite" / "modules.txt").read_text(encoding="utf-8").strip() == "Workforce Suite"
    assert (APP_ROOT / "workforce_suite" / "workforce_suite" / "doctype" / "workforce_biometric_device" / "workforce_biometric_device.json").exists()
    assert (APP_ROOT / "workforce_suite" / "workforce_suite" / "doctype" / "workforce_employee_biometric" / "workforce_employee_biometric.json").exists()
    assert (APP_ROOT / "workforce_suite" / "workforce_suite" / "doctype" / "workforce_payroll_policy" / "workforce_payroll_policy.json").exists()

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
