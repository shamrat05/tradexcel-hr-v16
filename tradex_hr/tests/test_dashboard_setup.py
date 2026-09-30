import json
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP_ROOT))

from tradex_hr.install import (
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
    assert "Tradexcel Salary Coverage Board" in links
    assert REPORTS["Tradexcel Salary Coverage Board"]["report_type"] == "Script Report"
    assert REPORTS["Tradexcel Salary Coverage Board"].get("query") is None


def test_workspace_prioritizes_scoped_work_instead_of_overview_cards():
    blocks = workspace_blocks()
    assert not any(block["type"] == "chart" for block in blocks)
    assert len([block for block in blocks if block["type"] == "number_card"]) == 0
    assert [block["data"]["custom_block_name"] for block in blocks if block["type"] == "custom_block"] == ["Tradexcel Work Needing Attention"]
    assert not any("Overview" in block.get("data", {}).get("text", "") for block in blocks)


def test_retired_artifacts_are_exactly_the_reviewed_allowlist():
    """TXUX-260930-013: no path may recreate a retired artifact."""
    assert {doctype for doctype, _names in RETIRED_ARTIFACTS} == {"Number Card", "Dashboard Chart"}
    assert set(RETIRED_NUMBER_CARDS) == {
        "Tradexcel Active Employees",
        "Tradexcel Punches Logged",
        "Tradexcel Present Records",
        "Tradexcel Absent Records",
        "TradeX Active Employees",
        "TradeX Punches Logged",
        "TradeX Present Records",
        "TradeX Absent Records",
        "Active Employees (All Companies)",
        "Active Employees-3",
        "Attendance Absent Logs-3",
        "Attendance Absent Logs-4",
        "Attendance Present Logs-3",
        "Attendance Present Logs-4",
        "EFL Active Employees",
        "EFL Active Employees-1",
        "Tradexcel EFL Active Employees",
        "TCL Active Employees",
        "TCL Active Employees-1",
        "Tradexcel TCL Active Employees",
        "Total Punches Logged-3",
        "Total Punches Logged-4",
        "TradeX EFL Active Employees",
        "TradeX TCL Active Employees",
    }
    assert set(RETIRED_DASHBOARD_CHARTS) == {
        "Tradexcel Employees by Department",
        "Tradexcel Employees by Branch",
        "Tradexcel Headcount by Company",
        "Tradexcel Attendance Status",
        "Tradexcel Leave Allocated by Type",
        "Tradexcel Payroll by Month",
        "Tradexcel Checkins by Day",
        "TradeX Employees by Department",
        "TradeX Employees by Branch",
        "TradeX Headcount by Company",
        "TradeX Attendance Status",
        "TradeX Leave Allocated by Type",
        "TradeX Payroll by Month",
        "TradeX Checkins by Day",
    }


def test_no_bundled_json_source_for_retired_artifacts():
    """Fresh installs cannot recreate the eleven records from app JSON files."""
    module_root = Path(__file__).resolve().parents[1] / "tradexcel_hr"
    assert not list(module_root.glob("dashboard_chart/*/*.json"))
    assert not list(module_root.glob("number_card/*/*.json"))


def test_retired_installer_creation_helpers_are_gone():
    """The installer no longer contains creation/rename paths for the eleven."""
    from tradex_hr import install

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

    report_root = Path(__file__).resolve().parents[1] / "tradexcel_hr" / "report"
    report_files = list(report_root.glob("*/*.json"))
    definitions = {
        definition["report_name"]: definition
        for path in report_files
        for definition in [json.loads(path.read_text())]
    }
    protected = {
        "Daily Attendance Summary",
        "Tradexcel Salary Coverage Board",
        "Biometric ID Audit",
        "Employee Data Gaps",
        "Workforce Anomaly Radar",
        "Tradexcel Shift Coverage",
        "Tradexcel Joiners and Leavers",
    }
    for name in protected:
        roles = {row["role"] for row in definitions[name]["roles"]}
        assert roles
        assert not roles.intersection({"Employee", "Employee Self Service"})


def test_operational_reports_are_file_backed_and_not_query_definitions():
    reports = {"Tradexcel Shift Coverage", "Tradexcel Joiners and Leavers"}
    assert reports <= set(STANDARD_SCRIPT_REPORT_NAMES)
    assert not reports.intersection(REPORTS)
    report_root = Path(__file__).resolve().parents[1] / "tradexcel_hr" / "report"
    definitions = {
        definition["report_name"]: definition
        for path in report_root.glob("*/*.json")
        for definition in [json.loads(path.read_text())]
    }
    expected = {
        "Tradexcel Shift Coverage": {
            "Tradexcel Owner/Director", "Tradexcel HR Manager",
            "Tradexcel HR/Attendance Officer", "Tradexcel Factory Supervisor",
            "Tradexcel Branch Manager", "Tradexcel Department Manager",
            "Tradexcel Compliance Auditor",
        },
        "Tradexcel Joiners and Leavers": {
            "Tradexcel Owner/Director", "Tradexcel HR Manager",
            "Tradexcel HR/Attendance Officer", "Tradexcel Branch Manager",
            "Tradexcel Department Manager", "Tradexcel Compliance Auditor",
        },
    }
    for name in reports:
        definition = definitions[name]
        assert definition["report_type"] == "Script Report"
        assert definition["is_standard"] == "Yes"
        assert definition["ref_doctype"] == "Employee"
        roles = {row["role"] for row in definition["roles"]}
        assert roles == expected[name]
        assert "Tradexcel Employee/Worker" not in roles


def test_only_canonical_tradexcel_workspace_is_managed():
    assert set(WORKSPACE_NAMES) == {"tradexcel-hr"}
    assert CANONICAL_WORKSPACE_NAME == "tradexcel-hr"


def test_only_canonical_workspace_is_visible_in_desk_navigation():
    assert workspace_is_visible("tradexcel-hr") is True
    assert workspace_is_visible("tradex-hr") is False
    assert workspace_is_visible("HR") is False
    assert workspace_is_visible("TradeX HR Management") is False
    assert workspace_is_visible("tradex-hr-management") is False


def test_title_named_workspace_is_retired():
    assert "Tradexcel HR" in LEGACY_WORKSPACE_NAMES
