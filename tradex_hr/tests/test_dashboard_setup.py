import json
import sys
from pathlib import Path


APP_ROOT = Path(r"\\wsl.localhost\Ubuntu\home\sanchita\frappe-bench\apps\tradex_hr")
sys.path.insert(0, str(APP_ROOT))

from tradex_hr.install import (
    DASHBOARD_CHARTS,
    NUMBER_CARDS,
    REPORTS,
    CANONICAL_WORKSPACE_NAME,
    WORKSPACE_NAMES,
    WORKSPACE_SHORTCUTS,
    workspace_blocks,
    workspace_is_visible,
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


def test_dashboard_has_company_specific_headcount_cards():
    assert {"Tradexcel Active Employees", "Tradexcel TCL Active Employees", "Tradexcel EFL Active Employees"} <= set(NUMBER_CARDS)


def test_only_canonical_tradexcel_workspace_is_managed():
    assert set(WORKSPACE_NAMES) == {"tradexcel-hr"}
    assert CANONICAL_WORKSPACE_NAME == "tradexcel-hr"


def test_only_canonical_workspace_is_visible_in_desk_navigation():
    assert workspace_is_visible("tradexcel-hr") is True
    assert workspace_is_visible("tradex-hr") is False
    assert workspace_is_visible("HR") is False
    assert workspace_is_visible("TradeX HR Management") is False
    assert workspace_is_visible("tradex-hr-management") is False
