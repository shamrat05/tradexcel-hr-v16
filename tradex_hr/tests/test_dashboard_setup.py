import json
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP_ROOT))

from tradex_hr.install import (
    DASHBOARD_CHARTS,
    NUMBER_CARDS,
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


def test_workspace_contains_actionable_number_cards_and_charts():
    blocks = workspace_blocks()
    types = [block["type"] for block in blocks]
    chart_names = {
        block["data"]["chart_name"]
        for block in blocks
        if block["type"] == "chart"
    }
    card_names = {
        block["data"]["number_card_name"]
        for block in blocks
        if block["type"] == "number_card"
    }

    assert types.count("number_card") >= 4
    assert types.count("chart") >= 4
    assert "Tradexcel Employees by Department" in chart_names
    assert "Tradexcel Payroll by Month" in chart_names
    assert "Tradexcel Active Employees" in card_names


def test_dashboard_chart_definitions_are_serializable():
    for definition in DASHBOARD_CHARTS.values():
        json.dumps(definition)
        assert definition["filters_json"].startswith("[")


def test_dashboard_does_not_ship_company_specific_headcount_cards():
    assert "Tradexcel Active Employees" in NUMBER_CARDS
    assert not {"Tradexcel TCL Active Employees", "Tradexcel EFL Active Employees"}.intersection(NUMBER_CARDS)
    assert not {"Tradexcel TCL Active Employees", "Tradexcel EFL Active Employees"}.intersection(
        block["data"].get("number_card_name") for block in workspace_blocks()
    )


def test_app_owned_dashboard_records_are_custom_records():
    """Runtime install must work on Frappe v16 without developer mode."""
    assert all(values.get("is_standard") == 0 for values in NUMBER_CARDS.values())
    assert all(values.get("is_standard", 0) == 0 for values in DASHBOARD_CHARTS.values())
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
