import json
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP_ROOT))

from workforce_suite.install import (
    RETIRED_ARTIFACTS,
    RETIRED_DASHBOARD_CHARTS,
    RETIRED_NUMBER_CARDS,
    REPORTS,
    CANONICAL_WORKSPACE_NAME,
    WORKSPACE_NAMES,
    LEGACY_WORKSPACE_NAMES,
    WORKSPACE_SHORTCUTS,
    workspace_blocks,
    workspace_is_visible,
    STANDARD_SCRIPT_REPORT_NAMES,
)


def test_workspace_has_salary_setup_shortcuts():
    links = {link_to for _label, link_to, _link_type in WORKSPACE_SHORTCUTS}

    assert {
        "Salary Component",
        "Salary Structure",
        "Salary Structure Assignment",
        "Additional Salary",
        "Payroll Entry",
        "Salary Slip",
    } <= links
    assert "Workforce Salary Coverage Board" in links
    assert REPORTS["Workforce Salary Coverage Board"]["report_type"] == "Script Report"
    assert REPORTS["Workforce Salary Coverage Board"].get("query") is None


def test_workspace_prioritizes_scoped_work_instead_of_overview_cards():
    blocks = workspace_blocks()
    assert not any(block["type"] == "chart" for block in blocks)
    assert len([block for block in blocks if block["type"] == "number_card"]) == 0
    assert [block["data"]["custom_block_name"] for block in blocks if block["type"] == "custom_block"] == ["Workforce Work Needing Attention"]
    assert not any("Overview" in block.get("data", {}).get("text", "") for block in blocks)


def test_retired_artifacts_are_exactly_the_reviewed_allowlist():
    """TXUX-260930-013: no path may recreate a retired artifact."""
    assert {doctype for doctype, _names in RETIRED_ARTIFACTS} == {"Number Card", "Dashboard Chart"}
    assert set(RETIRED_NUMBER_CARDS) == {
        "Workforce Active Employees",
        "Workforce Punches Logged",
        "Workforce Present Records",
        "Workforce Absent Records",
    }
    assert set(RETIRED_DASHBOARD_CHARTS) == {
        "Workforce Employees by Department",
        "Workforce Employees by Branch",
        "Workforce Headcount by Company",
        "Workforce Attendance Status",
        "Workforce Leave Allocated by Type",
        "Workforce Payroll by Month",
        "Workforce Checkins by Day",
    }


def test_no_bundled_json_source_for_retired_artifacts():
    """Fresh installs cannot recreate the eleven records from app JSON files."""
    module_root = Path(__file__).resolve().parents[1] / "workforce_suite"
    assert not list(module_root.glob("dashboard_chart/*/*.json"))
    assert not list(module_root.glob("number_card/*/*.json"))


def test_retired_installer_creation_helpers_are_gone():
    """The installer no longer contains creation/rename paths for the eleven."""
    from workforce_suite import install

    for helper in (
        "ensure_number_cards",
        "ensure_dashboard_charts",
        "rename_legacy_dashboard_charts",
        "rename_legacy_number_cards",
        "remove_orphaned_dashboard_records",
    ):
        assert not hasattr(install, helper), f"{helper} must be retired"
    assert not hasattr(install, "NUMBER_CARDS")
    assert not hasattr(install, "DASHBOARD_CHARTS")
    assert hasattr(install, "remove_retired_dashboard_artifacts")


def test_workspace_home_declares_no_snapshot_cards():
    assert not any(block["type"] == "number_card" for block in workspace_blocks())
    assert not any(block["type"] == "chart" for block in workspace_blocks())


def test_app_owned_reports_declare_their_standard_flag():
    """Runtime install must work on Frappe v16 without developer mode."""
    assert all(
        config.get("is_standard", "No") == ("Yes" if config.get("report_type") == "Script Report" else "No")
        for config in REPORTS.values()
    )


def test_python_script_reports_are_app_owned_standard_reports():
    """Bundled execute() reports must not depend on disabled Server Scripts."""
    script_reports = {
        name for name, config in REPORTS.items() if config.get("report_type") == "Script Report"
    }
    assert script_reports
    assert all(REPORTS[name].get("is_standard") == "Yes" for name in script_reports)


def test_sensitive_standard_reports_have_explicit_non_employee_roles():
    """Standard reports must not silently become public when roles are empty."""
    import json

    report_root = Path(__file__).resolve().parents[1] / "workforce_suite" / "report"
    report_files = list(report_root.glob("*/*.json"))
    definitions = {
        definition["report_name"]: definition
        for path in report_files
        for definition in [json.loads(path.read_text())]
    }
    protected = {
        "Daily Attendance Summary",
        "Workforce Salary Coverage Board",
        "Biometric ID Audit",
        "Employee Data Gaps",
        "Workforce Anomaly Radar",
        "Workforce Shift Coverage",
        "Workforce Joiners and Leavers",
    }
    for name in protected:
        roles = {row["role"] for row in definitions[name]["roles"]}
        assert roles
        assert not roles.intersection({"Employee", "Employee Self Service"})


def test_operational_reports_are_file_backed_and_not_query_definitions():
    reports = {"Workforce Shift Coverage", "Workforce Joiners and Leavers"}
    assert reports <= set(STANDARD_SCRIPT_REPORT_NAMES)
    assert not reports.intersection(REPORTS)
    report_root = Path(__file__).resolve().parents[1] / "workforce_suite" / "report"
    definitions = {
        definition["report_name"]: definition
        for path in report_root.glob("*/*.json")
        for definition in [json.loads(path.read_text())]
    }
    expected = {
        "Workforce Shift Coverage": {
            "Workforce Owner/Director", "Workforce Suite Manager",
            "Workforce Suite/Attendance Officer", "Workforce Factory Supervisor",
            "Workforce Branch Manager", "Workforce Department Manager",
            "Workforce Compliance Auditor",
        },
        "Workforce Joiners and Leavers": {
            "Workforce Owner/Director", "Workforce Suite Manager",
            "Workforce Suite/Attendance Officer", "Workforce Branch Manager",
            "Workforce Department Manager", "Workforce Compliance Auditor",
        },
    }
    for name in reports:
        definition = definitions[name]
        assert definition["report_type"] == "Script Report"
        assert definition["is_standard"] == "Yes"
        assert definition["ref_doctype"] == "Employee"
        roles = {row["role"] for row in definition["roles"]}
        assert roles == expected[name]
        assert "Workforce Employee/Worker" not in roles


def test_only_canonical_workforce_workspace_is_managed():
    assert set(WORKSPACE_NAMES) == {"workforce-suite"}
    assert CANONICAL_WORKSPACE_NAME == "workforce-suite"


def test_only_canonical_workspace_is_visible_in_desk_navigation():
    assert workspace_is_visible("workforce-suite") is True
    assert workspace_is_visible("workforce-hr") is False
    assert workspace_is_visible("HR") is False
    assert workspace_is_visible("workforce-hr-management") is False


def test_title_named_workspace_is_retired():
    assert "Workforce Suite" in LEGACY_WORKSPACE_NAMES
