"""Install-time reports and the Tradexcel HR action-board workspace."""

from __future__ import annotations

import json

import frappe


BIOMETRIC_ID_AUDIT_JAVASCRIPT = """
frappe.query_reports["Biometric ID Audit"] = {
  filters: [
    {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: "", reqd: 0},
    {fieldname: "device", label: __("Device"), fieldtype: "Link", options: "Tradexcel Biometric Device", default: "", reqd: 0},
    {fieldname: "employee_status", label: __("Employee Status"), fieldtype: "Select", options: "All\\nActive\\nInactive\\nLeft", default: "Active"},
    {fieldname: "assignment_status", label: __("Assignment Status"), fieldtype: "Select", options: "All\\nAssigned\\nUnassigned\\nDuplicate\\nLegacy", default: "All"},
    {fieldname: "show_duplicates", label: __("Show Duplicates Only"), fieldtype: "Select", options: "No\\nYes", default: "No"}
  ],
  onload: function(report) {
    report.page.add_inner_button(__("Assign Biometric ID"), function() {
      frappe.prompt([
        {fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee", reqd: 1},
        {fieldname: "device", label: __("Device"), fieldtype: "Link", options: "Tradexcel Biometric Device", reqd: 1},
        {fieldname: "biometric_id", label: __("Biometric ID / PIN"), fieldtype: "Data", reqd: 1}
      ], function(values) {
        frappe.call({method: "tradex_hr.api.assign_employee_biometric", args: values}).then(function() {
          frappe.show_alert({message: __("Device-specific biometric assignment saved"), indicator: "green"});
          report.refresh();
        });
      }, __("Assign Biometric ID"), __("Save"));
    });
    report.page.add_inner_button(__("Copy Biometric to Device"), function() {
      frappe.prompt([
        {fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee", reqd: 1},
        {fieldname: "source_device", label: __("Copy From Device"), fieldtype: "Link", options: "Tradexcel Biometric Device", reqd: 1},
        {fieldname: "target_device", label: __("Copy To Device"), fieldtype: "Link", options: "Tradexcel Biometric Device", reqd: 1},
        {fieldname: "target_biometric_id", label: __("Target Biometric ID / PIN"), fieldtype: "Data"}
      ], function(values) {
        frappe.confirm(__("This queues biometric templates to the target device. Continue?"), function() {
          frappe.call({
            method: "tradex_hr.api.transfer_employee_biometric",
            args: Object.assign({}, values, {confirm_transfer: 1})
          }).then(function() {
            frappe.show_alert({message: __("Biometric transfer queued"), indicator: "green"});
            report.refresh();
          });
        });
      }, __("Copy Biometric to Device"), __("Queue Transfer"));
    });
  }
};
"""

REPORTS = {
    "Tradexcel Salary Coverage Board": {
        "ref_doctype": "Employee",
        "report_type": "Script Report",
        # This report has a bundled Python execute() module. It must remain a
        # standard app report; custom Script Reports require Server Scripts.
        "is_standard": "Yes",
        "javascript": """
frappe.query_reports[\"Tradexcel Salary Coverage Board\"] = {
  filters: [
    {fieldname: \"company\", label: __(\"Company\"), fieldtype: \"Link\", options: \"Company\", default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default(\"Company\")) || \"\", reqd: 1},
    {fieldname: \"as_of_date\", label: __(\"As Of Date\"), fieldtype: \"Date\", default: frappe.datetime.get_today(), reqd: 1},
    {fieldname: \"employee_status\", label: __(\"Employee Status\"), fieldtype: \"Select\", options: \"All\\nActive\\nInactive\\nLeft\", default: \"Active\"},
    {fieldname: "assignment_status", label: __("Assignment Status"), fieldtype: "Select", options: "All\\nAssigned\\nMissing\\nCompany Mismatch", default: "All"},
    {fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch", default: "", get_query: function() { var c = frappe.query_report.get_filter_value('company'); return c ? {filters: {company: c}} : {}; }},
    {fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department", default: "", get_query: function() { var company = frappe.query_report.get_filter_value('company'); var branch = frappe.query_report.get_filter_value('branch'); if (!branch) { return company ? {filters: {company: company}} : {}; } return {query: 'tradex_hr.link_filters.departments_used_by_branch', filters: {company: company, branch: branch}}; }}
  ]
};
""",
    },
    "Biometric ID Audit": {
        "ref_doctype": "Employee",
        "report_type": "Script Report",
        "is_standard": "Yes",
        "javascript": BIOMETRIC_ID_AUDIT_JAVASCRIPT,
    },
    "Employee Data Gaps": {
        "ref_doctype": "Employee",
        "report_type": "Script Report",
        "is_standard": "Yes",
    },
    "Workforce Anomaly Radar": {
        "ref_doctype": "Employee",
        "report_type": "Script Report",
        "is_standard": "Yes",
    },
}

LEGACY_REPORT_NAMES = {
    "TradeX Daily Attendance Board": "Tradexcel Daily Attendance Board",
    "TradeX Payroll Register": "Tradexcel Payroll Register",
    "TradeX Salary Coverage Board": "Tradexcel Salary Coverage Board",
    "TradeX Leave Balance Board": "Tradexcel Leave Balance Board",
}

STANDARD_SCRIPT_REPORT_NAMES = (
    "Daily Attendance Summary",
    "Tradexcel Salary Coverage Board",
    "Biometric ID Audit",
    "Employee Data Gaps",
    "Workforce Anomaly Radar",
    "Tradexcel Payroll Readiness",
    # Promoted from DB-backed Query Reports. Script Reports reload from their
    # standard app JSON, which converges existing custom Query Report metadata.
    "Tradexcel Payroll Register",
    "Tradexcel Leave Balance Board",
    "Tradexcel Daily Attendance Board",
    "Tradexcel Shift Coverage",
    "Tradexcel Joiners and Leavers",
    "Tradexcel Pay Component Register",
    "Tradexcel Payroll Variance",
)


def ensure_standard_script_reports() -> None:
    """Restore app-owned Python reports from their file-backed definitions.

    Frappe executes a standard Script Report through its app module. A custom
    Script Report instead executes ``report_script`` with safe_exec, which is
    disabled by default in v16. Older migrations demoted some bundled reports;
    repair only those known app-owned records, then let the JSON files remain
    the source of truth on future migrations.
    """
    for report_name in STANDARD_SCRIPT_REPORT_NAMES:
        if frappe.db.exists("Report", report_name):
            doc = frappe.get_doc("Report", report_name)
            if doc.is_standard != "Yes":
                if doc.module not in (None, "", "Tradexcel HR"):
                    frappe.throw(
                        f"Cannot repair standard report {report_name!r} owned by module {doc.module!r}"
                    )
                frappe.delete_doc("Report", report_name, force=True, ignore_permissions=True)
        # Always reload the app-owned JSON so role-table changes self-heal on
        # existing standard reports without converting them to custom reports.
        frappe.reload_doc("tradexcel_hr", "report", frappe.scrub(report_name), force=True)
        # The standard report JSON is the source of filter defaults. Legacy
        # company-specific JavaScript rewriting is no longer needed.

NUMBER_CARDS = {
    "Tradexcel Active Employees": {
        "label": "Active Employees (All Companies)",
        "type": "Document Type",
        "document_type": "Employee",
        "function": "Count",
        "filters_json": json.dumps([
            ["Employee", "status", "=", "Active", False],
        ]),
        "is_standard": 0,
        "module": "Tradexcel HR",
        "is_public": 1,
        "color": "Green",
    },
    "Tradexcel Punches Logged": {
        "label": "Total Punches Logged",
        "type": "Document Type",
        "document_type": "Employee Checkin",
        "function": "Count",
        "filters_json": json.dumps([["Employee Checkin", "docstatus", "<", "2", False]]),
        "is_standard": 0,
        "module": "Tradexcel HR",
        "is_public": 1,
        "color": "Blue",
    },
    "Tradexcel Present Records": {
        "label": "Attendance Present Logs",
        "type": "Document Type",
        "document_type": "Attendance",
        "function": "Count",
        "filters_json": json.dumps([
            ["Attendance", "status", "=", "Present", False],
        ]),
        "is_standard": 0,
        "module": "Tradexcel HR",
        "is_public": 1,
        "color": "Cyan",
    },
    "Tradexcel Absent Records": {
        "label": "Attendance Absent Logs",
        "type": "Document Type",
        "document_type": "Attendance",
        "function": "Count",
        "filters_json": json.dumps([
            ["Attendance", "status", "=", "Absent", False],
        ]),
        "is_standard": 0,
        "module": "Tradexcel HR",
        "is_public": 1,
        "color": "Red",
    },
}

LEGACY_NUMBER_CARD_NAMES = {
    "TradeX Active Employees": "Tradexcel Active Employees",
    "TradeX Punches Logged": "Tradexcel Punches Logged",
    "TradeX Present Records": "Tradexcel Present Records",
    "TradeX Absent Records": "Tradexcel Absent Records",
}

# These are duplicate records created by the prototype dashboard setup. They
# are intentionally explicit so future migrations never delete a genuinely
# user-created card or chart in the Tradexcel HR module.
ORPHANED_NUMBER_CARD_NAMES = (
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
    "TradeX Absent Records",
    "TradeX Active Employees",
    "TradeX EFL Active Employees",
    "TradeX Present Records",
    "TradeX Punches Logged",
    "TradeX TCL Active Employees",
)


DASHBOARD_CHARTS = {
    "Tradexcel Employees by Department": {
        "chart_type": "Group By",
        "document_type": "Employee",
        "group_by_type": "Count",
        "group_by_based_on": "department",
        "type": "Bar",
        "filters_json": json.dumps([
            ["Employee", "status", "=", "Active", False],
        ]),
    },
    "Tradexcel Employees by Branch": {
        "chart_type": "Group By",
        "document_type": "Employee",
        "group_by_type": "Count",
        "group_by_based_on": "branch",
        "type": "Bar",
        "filters_json": json.dumps([
            ["Employee", "status", "=", "Active", False],
        ]),
    },
    "Tradexcel Headcount by Company": {
        "chart_type": "Group By",
        "document_type": "Employee",
        "group_by_type": "Count",
        "group_by_based_on": "company",
        "type": "Pie",
        "filters_json": json.dumps([["Employee", "status", "=", "Active", False]]),
    },
    "Tradexcel Attendance Status": {
        "chart_type": "Group By",
        "document_type": "Attendance",
        "group_by_type": "Count",
        "group_by_based_on": "status",
        "type": "Pie",
        "filters_json": json.dumps([]),
    },
    "Tradexcel Leave Allocated by Type": {
        "chart_type": "Group By",
        "document_type": "Leave Allocation",
        "group_by_type": "Sum",
        "group_by_based_on": "leave_type",
        "aggregate_function_based_on": "total_leaves_allocated",
        "type": "Bar",
        "filters_json": json.dumps([]),
    },
    "Tradexcel Payroll by Month": {
        "chart_type": "Sum",
        "document_type": "Salary Slip",
        "based_on": "start_date",
        "value_based_on": "net_pay",
        "timeseries": 1,
        "timespan": "Last Year",
        "time_interval": "Monthly",
        "type": "Line",
        "filters_json": json.dumps([["Salary Slip", "docstatus", "=", "1", False]]),
    },
    "Tradexcel Checkins by Day": {
        "chart_type": "Count",
        "document_type": "Employee Checkin",
        "based_on": "time",
        "timeseries": 1,
        "timespan": "Last Month",
        "time_interval": "Daily",
        "type": "Line",
        "filters_json": json.dumps([["Employee Checkin", "docstatus", "<", "2", False]]),
    },
}


LEGACY_DASHBOARD_CHART_NAMES = {
    "TradeX Employees by Department": "Tradexcel Employees by Department",
    "TradeX Employees by Branch": "Tradexcel Employees by Branch",
    "TradeX Headcount by Company": "Tradexcel Headcount by Company",
    "TradeX Attendance Status": "Tradexcel Attendance Status",
    "TradeX Leave Allocated by Type": "Tradexcel Leave Allocated by Type",
    "TradeX Payroll by Month": "Tradexcel Payroll by Month",
    "TradeX Checkins by Day": "Tradexcel Checkins by Day",
}


WORKSPACE_SHORTCUTS = [
    ("Today's Attendance", "Tradexcel Daily Attendance Board", "Report"),
    ("Attendance Summary", "Daily Attendance Summary", "Report"),
    ("Mobile Attendance", "tradexcel-mobile-attendance", "Page"),
    ("Live Locations", "tradex-live-locations", "Page"),
    ("Punch Log", "Employee Checkin", "DocType"),
    ("Attendance Records", "Attendance", "DocType"),
    ("Employee Directory", "Employee", "DocType"),
    ("Departments", "Department", "DocType"),
    ("Designations", "Designation", "DocType"),
    ("Branches / Locations", "Branch", "DocType"),
    ("Joiners & Leavers", "Tradexcel Joiners and Leavers", "Report"),
    ("Employee Transfers", "Employee Transfer", "DocType"),
    ("Exits / Separations", "Employee Separation", "DocType"),
    ("Final Settlements", "Full and Final Statement", "DocType"),
    ("Run Monthly Payroll", "Tradexcel Payroll Readiness", "Report"),
    ("Payroll Entries (Advanced)", "Payroll Entry", "DocType"),
    ("Salary Slips", "Salary Slip", "DocType"),
    ("Salary Structures", "Salary Structure", "DocType"),
    ("Salary Assignments", "Salary Structure Assignment", "DocType"),
    ("Salary Components", "Salary Component", "DocType"),
    ("Extra Pay & Deductions", "Additional Salary", "DocType"),
    ("Payroll Register", "Tradexcel Payroll Register", "Report"),
    ("Payroll Variance", "Tradexcel Payroll Variance", "Report"),
    ("Pay Component Register", "Tradexcel Pay Component Register", "Report"),
    ("Salary Setup Coverage", "Tradexcel Salary Coverage Board", "Report"),
    ("Payroll Rules", "Tradexcel Payroll Policy", "DocType"),
    ("Policy Exceptions", "Tradexcel Policy Exception", "DocType"),
    ("Leave Requests", "Leave Application", "DocType"),
    ("Leave Allocations", "Leave Allocation", "DocType"),
    ("Leave Balances", "Tradexcel Leave Balance Board", "Report"),
    ("Shift Types", "Shift Type", "DocType"),
    ("Shift Planner", "Shift Schedule", "DocType"),
    ("Shift Assignments", "Shift Schedule Assignment", "DocType"),
    ("Shift Coverage", "Tradexcel Shift Coverage", "Report"),
    ("Attendance Policies", "Tradexcel Attendance Policy", "DocType"),
    ("Field Duties", "Tradexcel Field Duty", "DocType"),
    ("Location Pings", "Tradexcel Location Ping", "DocType"),
    ("Anomaly Radar", "Workforce Anomaly Radar", "Report"),
    ("Missing Employee Data", "Employee Data Gaps", "Report"),
    ("Biometric ID Audit", "Biometric ID Audit", "Report"),
    ("Biometric Devices", "Tradexcel Biometric Device", "DocType"),
    ("Employee Biometric IDs", "Tradexcel Employee Biometric", "DocType"),
    ("Face Match Settings", "Tradex Face Match Settings", "DocType"),
    ("Bulk Data Import", "Data Import", "DocType"),
]

BULK_WORKSPACE_SHORTCUTS = [
    ("Bulk Salary Structure Assignment", "Bulk Salary Structure Assignment", "DocType"),
    ("Attendance Fix Requests", "Attendance Request", "DocType"),
    ("Bulk Leave Allocation", "Leave Control Panel", "DocType"),
    ("Bulk Shift Assignment", "Shift Assignment Tool", "DocType"),
]

# Frappe stores icons on Workspace Shortcut rows. These names are from the
# installed timeless icon set, so no custom icon bundle is needed.
WORKSPACE_SHORTCUT_ICONS = {
    "Today's Attendance": "today",
    "Attendance Summary": "calendar",
    "Mobile Attendance": "location",
    "Live Locations": "map",
    "Punch Log": "scan",
    "Attendance Records": "check",
    "Attendance Fix Requests": "clipboard",
    "Employee Directory": "users",
    "Departments": "organization",
    "Designations": "hr",
    "Branches / Locations": "branch",
    "Joiners & Leavers": "change",
    "Employee Transfers": "assign",
    "Exits / Separations": "remove",
    "Final Settlements": "money-coins-1",
    "Run Monthly Payroll": "accounting",
    "Payroll Entries (Advanced)": "file",
    "Salary Slips": "file",
    "Salary Structures": "income",
    "Salary Assignments": "assign",
    "Salary Components": "money-coins-1",
    "Extra Pay & Deductions": "money-coins-1",
    "Payroll Register": "list-alt",
    "Payroll Variance": "chart",
    "Pay Component Register": "clipboard",
    "Salary Setup Coverage": "check",
    "Payroll Rules": "setting-gear",
    "Policy Exceptions": "workflow",
    "Leave Requests": "clipboard",
    "Leave Allocations": "assign",
    "Leave Balances": "chart",
    "Shift Types": "hr",
    "Shift Planner": "calendar",
    "Shift Assignments": "assign",
    "Bulk Leave Allocation": "assign",
    "Bulk Shift Assignment": "assign",
    "Bulk Salary Structure Assignment": "assign",
    "Shift Coverage": "check",
    "Attendance Policies": "setting-gear",
    "Field Duties": "location",
    "Location Pings": "map",
    "Anomaly Radar": "solid-warning",
    "Missing Employee Data": "solid-warning",
    "Biometric ID Audit": "scan",
    "Biometric Devices": "integration",
    "Employee Biometric IDs": "users",
    "Face Match Settings": "setting-gear",
    "Bulk Data Import": "upload",
    "Attendance Fix Requests": "clipboard",
}

WORKSPACE_SECTIONS = (
    ("Every day", "Start here: attendance, missing punches, and corrections.", (
        "Today's Attendance", "Attendance Summary", "Mobile Attendance", "Live Locations", "Punch Log", "Attendance Records", "Attendance Fix Requests",
    )),
    ("Field & mobile", "Use GPS, field duties, live positions, and biometric evidence without affecting terminal punches.", (
        "Attendance Policies", "Field Duties", "Location Pings", "Face Match Settings",
    )),
    ("People", "Employees, organization structure, movement, and exits.", (
        "Employee Directory", "Departments", "Designations", "Branches / Locations",
        "Joiners & Leavers", "Employee Transfers", "Exits / Separations", "Final Settlements",
    )),
    ("Payroll & salary", "Prepare payroll, maintain pay rules, and review every amount.", (
        "Run Monthly Payroll", "Payroll Entries (Advanced)", "Salary Slips", "Salary Structures", "Salary Assignments",
        "Salary Components", "Extra Pay & Deductions", "Payroll Register", "Payroll Variance",
        "Pay Component Register", "Salary Setup Coverage", "Payroll Rules", "Policy Exceptions",
        "Bulk Salary Structure Assignment",
    )),
    ("Leave & shifts", "Plan shifts, allocate leave, and check coverage before payroll.", (
        "Leave Requests", "Leave Allocations", "Bulk Leave Allocation", "Leave Balances",
        "Shift Types", "Shift Planner", "Shift Assignments", "Bulk Shift Assignment", "Shift Coverage",
    )),
    ("Checks & alerts", "Review exceptions before they become payroll or attendance mistakes.", (
        "Anomaly Radar", "Missing Employee Data", "Biometric ID Audit",
    )),
    ("Devices & data", "Connect attendance devices and safely fill verified master data.", (
        "Biometric Devices", "Employee Biometric IDs", "Bulk Data Import", "Attendance Requests",
    )),
)


WORKSPACE_NAMES = {
    "tradexcel-hr": {"title": "Tradexcel HR", "module": "Tradexcel HR"},
}
LEGACY_WORKSPACE_NAMES = (
    # The prototype also created a title-named copy. Keep only the canonical
    # slug workspace so Desk has one unambiguous HR entry point.
    "Tradexcel HR",
    "tradex-hr",
    "TradeX HR Management",
    "tradex-hr-management",
)
CANONICAL_WORKSPACE_NAME = "tradexcel-hr"


def workspace_is_visible(name: str) -> bool:
    """Keep one managed HR workspace in Desk navigation."""
    return name == CANONICAL_WORKSPACE_NAME


def workspace_blocks(shortcuts=None):
    """Return the dashboard layout used by both fresh installs and migrations."""
    shortcuts = shortcuts if shortcuts is not None else list(WORKSPACE_SHORTCUTS) + list(BULK_WORKSPACE_SHORTCUTS)
    available = {row[0]: row for row in shortcuts}
    blocks = [{"type": "header", "data": {"text": "<h2>Tradexcel HR Action Board</h2>", "col": 12}}]
    blocks.append({"type": "custom_block", "data": {"custom_block_name": "Tradexcel Work Needing Attention", "col": 12}})
    for title, description, labels in WORKSPACE_SECTIONS:
        blocks.append({"type": "header", "data": {"text": f"<h3>{title}</h3>", "col": 12}})
        blocks.append({"type": "paragraph", "data": {"text": description, "col": 12}})
        blocks.extend(
            {"type": "shortcut", "data": {"shortcut_name": label, "col": 3}}
            for label in labels
            if label in available
        )
    return blocks


def _ensure_custom_report(values: dict) -> None:
    """Create/update an app-owned report, including v15->v16 conversion.

    Older prototype installs marked these records as standard. Frappe v16
    correctly refuses to edit a standard report through the Desk. Query
    reports remain custom records, while app-owned Python Script Reports are
    kept standard so Frappe loads their bundled ``execute`` function without
    requiring the unsafe Server Scripts feature. A record owned by another
    module is never silently deleted.
    """
    values = dict(values)
    roles = values.pop("roles", None)
    report_name = values["report_name"]
    if frappe.db.exists("Report", report_name):
        doc = frappe.get_doc("Report", report_name)
        if doc.is_standard == "Yes" and values.get("is_standard") == "No":
            if doc.module not in (None, "", "Tradexcel HR"):
                frappe.throw(
                    f"Cannot replace standard report {report_name!r} owned by module {doc.module!r}"
                )
            frappe.delete_doc("Report", report_name, force=True, ignore_permissions=True)
            doc = frappe.get_doc({"doctype": "Report", **values})
        else:
            for key, value in values.items():
                setattr(doc, key, value)
    else:
        doc = frappe.get_doc({"doctype": "Report", **values})

    if roles is not None:
        doc.roles = []
        for role in roles:
            doc.append("roles", {"role": role})
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)


def ensure_reports() -> None:
    ensure_standard_script_reports()
    for name, config in REPORTS.items():
        if config.get("is_standard") == "Yes":
            continue
        values = {
            "report_name": name, "ref_doctype": config["ref_doctype"],
            "report_type": config.get("report_type", "Query Report"),
            "is_standard": config.get("is_standard", "No"), "module": "Tradexcel HR",
            "query": config.get("query"), "report_script": config.get("report_script"),
            "javascript": config["javascript"], "disabled": 0,
        }
        if "roles" in config:
            values["roles"] = config["roles"]
        _ensure_custom_report(values)


def ensure_number_cards() -> None:
    for name, values in NUMBER_CARDS.items():
        payload = {"doctype": "Number Card", **values}
        if frappe.db.exists("Number Card", name):
            doc = frappe.get_doc("Number Card", name)
            for key, value in payload.items():
                if key not in {"doctype", "name"}:
                    setattr(doc, key, value)
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.get_doc(payload)
            doc.insert(ignore_permissions=True)
            if doc.name != name:
                frappe.rename_doc("Number Card", doc.name, name, force=True)


def ensure_dashboard_charts() -> None:
    for name, values in DASHBOARD_CHARTS.items():
        payload = {
            "doctype": "Dashboard Chart",
            "chart_name": name,
            "is_standard": 0,
            "module": "Tradexcel HR",
            "is_public": 1,
            **values,
        }
        if frappe.db.exists("Dashboard Chart", name):
            doc = frappe.get_doc("Dashboard Chart", name)
            for key, value in payload.items():
                if key != "doctype":
                    setattr(doc, key, value)
            doc.save(ignore_permissions=True)
        else:
            frappe.get_doc(payload).insert(ignore_permissions=True)


def rename_legacy_dashboard_charts() -> None:
    """Rename managed chart records so the dashboard uses the Tradexcel brand."""
    for legacy_name, canonical_name in LEGACY_DASHBOARD_CHART_NAMES.items():
        if not frappe.db.exists("Dashboard Chart", legacy_name):
            continue
        if frappe.db.exists("Dashboard Chart", canonical_name):
            frappe.delete_doc(
                "Dashboard Chart", legacy_name, force=True, ignore_permissions=True
            )
        else:
            frappe.rename_doc(
                "Dashboard Chart", legacy_name, canonical_name, force=True
            )


def rename_legacy_number_cards() -> None:
    """Rename managed card records so the dashboard has one brand namespace."""
    for legacy_name, canonical_name in LEGACY_NUMBER_CARD_NAMES.items():
        if not frappe.db.exists("Number Card", legacy_name):
            continue
        if frappe.db.exists("Number Card", canonical_name):
            frappe.delete_doc("Number Card", legacy_name, force=True, ignore_permissions=True)
        else:
            frappe.rename_doc("Number Card", legacy_name, canonical_name, force=True)


def remove_orphaned_dashboard_records() -> None:
    """Remove known prototype duplicates after canonical records are ensured."""
    for doctype, names in (
        ("Number Card", ORPHANED_NUMBER_CARD_NAMES),
        ("Dashboard Chart", tuple(LEGACY_DASHBOARD_CHART_NAMES)),
    ):
        for name in names:
            if not frappe.db.exists(doctype, name):
                continue
            module = frappe.db.get_value(doctype, name, "module")
            if module == "Tradexcel HR":
                frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)


def rename_legacy_reports() -> None:
    """Retire old report names so Desk has one canonical Tradexcel route."""
    for legacy_name, canonical_name in LEGACY_REPORT_NAMES.items():
        if not frappe.db.exists("Report", legacy_name):
            continue
        if frappe.db.exists("Report", canonical_name):
            frappe.delete_doc("Report", legacy_name, force=True, ignore_permissions=True)
        else:
            frappe.rename_doc("Report", legacy_name, canonical_name, force=True)

def ensure_action_board_block() -> None:
    from pathlib import Path
    from tradex_hr.tradexcel_hr.action_board import BOARD_ROLES

    name = "Tradexcel Work Needing Attention"
    root = Path(__file__).parent / "public" / "action_board"
    doc = frappe.get_doc("Custom HTML Block", name) if frappe.db.exists("Custom HTML Block", name) else frappe.new_doc("Custom HTML Block")
    doc.name = name
    doc.private = 0
    doc.html = (root / "home.html").read_text()
    doc.script = (root / "home.js").read_text()
    doc.style = (root / "home.css").read_text()
    doc.set("roles", [{"role": role} for role in sorted(BOARD_ROLES)])
    doc.save(ignore_permissions=True)


def ensure_workspace() -> None:
    ensure_action_board_block()
    def save_workspace_doc(doc):
        # Frappe normally rejects duplicate workspace slugs during ordinary
        # edits.  These legacy aliases are explicitly retired for production.
        previous_in_migrate = frappe.flags.in_migrate
        frappe.flags.in_migrate = True
        try:
            if doc.is_new():
                doc.insert(ignore_permissions=True)
            else:
                doc.save(ignore_permissions=True)
        finally:
            frappe.flags.in_migrate = previous_in_migrate

    for legacy_name in LEGACY_WORKSPACE_NAMES:
        if frappe.db.exists("Workspace", legacy_name):
            frappe.delete_doc(
                "Workspace", legacy_name, force=True, ignore_permissions=True
            )

    shortcuts = list(WORKSPACE_SHORTCUTS) + [
        row for row in BULK_WORKSPACE_SHORTCUTS
        if frappe.db.exists("DocType", row[1])
    ]
    if not frappe.db.exists("DocType", "Tradexcel Biometric Device"):
        shortcuts = [row for row in shortcuts if row[1] != "Tradexcel Biometric Device"]
    content = json.dumps(workspace_blocks(shortcuts))
    for name, workspace_values in WORKSPACE_NAMES.items():
        if frappe.db.exists("Workspace", name):
            doc = frappe.get_doc("Workspace", name)
        else:
            doc = frappe.new_doc("Workspace")
            doc.name = name
            doc.label = name
            doc.title = workspace_values["title"]
            doc.module = workspace_values["module"]
            doc.icon = "users"
            doc.indicator_color = "blue"

        doc.content = content
        doc.type = "Workspace"
        doc.title = workspace_values["title"]
        doc.public = 1 if workspace_is_visible(name) else 0
        doc.is_hidden = 0 if workspace_is_visible(name) else 1
        doc.charts = []
        doc.number_cards = []
        doc.set("custom_blocks", [{"custom_block_name": "Tradexcel Work Needing Attention", "label": "Work needing attention"}])
        doc.shortcuts = []
        for label, link_to, link_type in shortcuts:
            doc.append("shortcuts", {
                "label": label,
                "link_to": link_to,
                "type": link_type,
                "icon": WORKSPACE_SHORTCUT_ICONS.get(label),
                "color": "Blue",
            })
        save_workspace_doc(doc)


def ensure_property_setters() -> dict[str, int]:
    """Make the app's Property Setters reproducible.

    These were previously created by hand and existed only in the database (five
    of them on Salary Structure Assignment, created 2026-09-17). Nothing in the
    app recreated them, so a fresh install or a Contabo deploy would silently
    lose the list-view sorting and standard filters.

    Idempotent: create if missing, correct the value if it drifted, leave alone
    if already right.
    """
    DOC = "Salary Structure Assignment"
    WANTED = [
        ("company", "in_standard_filter", "1"),
        ("department", "in_standard_filter", "1"),
        ("designation", "in_standard_filter", "1"),
        (None, "sort_field", "from_date"),
        (None, "sort_order", "DESC"),
    ]
    created = corrected = 0
    for field_name, prop, value in WANTED:
        name = frappe.db.get_value(
            "Property Setter",
            {"doc_type": DOC, "field_name": field_name, "property": prop},
            "name",
        )
        if name:
            current = frappe.db.get_value("Property Setter", name, "value")
            if str(current or "") != value:
                frappe.db.set_value("Property Setter", name, "value", value)
                corrected += 1
            continue
        prop_doc = frappe.new_doc("Property Setter")
        prop_doc.doctype_or_field = "DocField" if field_name else "DocType"
        prop_doc.doc_type = DOC
        prop_doc.field_name = field_name
        prop_doc.property = prop
        prop_doc.property_type = "Text"
        prop_doc.value = value
        prop_doc.flags.ignore_permissions = True
        prop_doc.insert()
        created += 1
    return {"created": created, "corrected": corrected}


def after_install():
    after_migrate()


def after_migrate():
    from tradex_hr.branch_setup import ensure_branch_fields
    from tradex_hr.role_setup import ensure_tradex_roles
    from tradex_hr.approval_setup import ensure_tradex_workflows
    from tradex_hr.field_attendance_setup import ensure_field_attendance_fields, ensure_field_transport_component
    from tradex_hr.field_financial_setup import (
        ensure_income_tax_review_fields,
        ensure_payroll_adjustment_workflow_fields,
    )
    from tradex_hr.field_employee_exit_setup import ensure_default_exit_template, ensure_employee_exit_fields
    from tradex_hr.field_working_time_setup import ensure_working_time_holiday_category_field

    ensure_branch_fields()
    ensure_tradex_roles()
    ensure_payroll_adjustment_workflow_fields()
    ensure_employee_exit_fields()
    ensure_tradex_workflows()
    ensure_default_exit_template()
    ensure_field_attendance_fields()
    ensure_field_transport_component()
    ensure_working_time_holiday_category_field()
    ensure_income_tax_review_fields()
    # Historic structure pay-basis seeding is an explicit reviewed migration
    # utility, not a generic install action on another company's structures.
    rename_legacy_dashboard_charts()
    ensure_reports()
    ensure_number_cards()
    ensure_dashboard_charts()
    rename_legacy_number_cards()
    rename_legacy_reports()
    remove_orphaned_dashboard_records()
    ensure_workspace()
    ensure_property_setters()
    frappe.db.commit()
    frappe.clear_cache()
