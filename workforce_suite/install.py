"""Install-time reports and the Workforce Suite action-board workspace."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import re

import frappe



BIOMETRIC_ID_AUDIT_JAVASCRIPT = """
frappe.query_reports["Biometric ID Audit"] = {
  filters: [
    {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: "", reqd: 0},
    {fieldname: "device", label: __("Device"), fieldtype: "Link", options: "Workforce Biometric Device", default: "", reqd: 0},
    {fieldname: "employee_status", label: __("Employee Status"), fieldtype: "Select", options: "All\\nActive\\nInactive\\nLeft", default: "Active"},
    {fieldname: "assignment_status", label: __("Assignment Status"), fieldtype: "Select", options: "All\\nAssigned\\nUnassigned\\nDuplicate\\nLegacy", default: "All"},
    {fieldname: "show_duplicates", label: __("Show Duplicates Only"), fieldtype: "Select", options: "No\\nYes", default: "No"}
  ],
  onload: function(report) {
    report.page.add_inner_button(__("Assign Biometric ID"), function() {
      frappe.prompt([
        {fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee", reqd: 1},
        {fieldname: "device", label: __("Device"), fieldtype: "Link", options: "Workforce Biometric Device", reqd: 1},
        {fieldname: "biometric_id", label: __("Biometric ID / PIN"), fieldtype: "Data", reqd: 1}
      ], function(values) {
        frappe.call({method: "workforce_suite.api.assign_employee_biometric", args: values}).then(function() {
          frappe.show_alert({message: __("Device-specific biometric assignment saved"), indicator: "green"});
          report.refresh();
        });
      }, __("Assign Biometric ID"), __("Save"));
    });
    report.page.add_inner_button(__("Copy Biometric to Device"), function() {
      frappe.prompt([
        {fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee", reqd: 1},
        {fieldname: "source_device", label: __("Copy From Device"), fieldtype: "Link", options: "Workforce Biometric Device", reqd: 1},
        {fieldname: "target_device", label: __("Copy To Device"), fieldtype: "Link", options: "Workforce Biometric Device", reqd: 1},
        {fieldname: "target_biometric_id", label: __("Target Biometric ID / PIN"), fieldtype: "Data"}
      ], function(values) {
        frappe.confirm(__("This queues biometric templates to the target device. Continue?"), function() {
          frappe.call({
            method: "workforce_suite.api.transfer_employee_biometric",
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
    "Workforce Salary Coverage Board": {
        "ref_doctype": "Employee",
        "report_type": "Script Report",
        # This report has a bundled Python execute() module. It must remain a
        # standard app report; custom Script Reports require Server Scripts.
        "is_standard": "Yes",
        "javascript": """
frappe.query_reports[\"Workforce Salary Coverage Board\"] = {
  filters: [
    {fieldname: \"company\", label: __(\"Company\"), fieldtype: \"Link\", options: \"Company\", default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default(\"Company\")) || \"\", reqd: 1},
    {fieldname: \"as_of_date\", label: __(\"As Of Date\"), fieldtype: \"Date\", default: frappe.datetime.get_today(), reqd: 1},
    {fieldname: \"employee_status\", label: __(\"Employee Status\"), fieldtype: \"Select\", options: \"All\\nActive\\nInactive\\nLeft\", default: \"Active\"},
    {fieldname: "assignment_status", label: __("Assignment Status"), fieldtype: "Select", options: "All\\nAssigned\\nMissing\\nCompany Mismatch", default: "All"},
    {fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch", default: "", get_query: function() { var c = frappe.query_report.get_filter_value('company'); return c ? {filters: {company: c}} : {}; }},
    {fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department", default: "", get_query: function() { var company = frappe.query_report.get_filter_value('company'); var branch = frappe.query_report.get_filter_value('branch'); if (!branch) { return company ? {filters: {company: company}} : {}; } return {query: 'workforce_suite.link_filters.departments_used_by_branch', filters: {company: company, branch: branch}}; }}
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

# Legacy report aliases are migrated by scripts/migrate_legacy_site.py,
# not by a generic app install (which must never mutate unknown customer reports).
LEGACY_REPORT_NAMES = {}

STANDARD_SCRIPT_REPORT_NAMES = (
    "Daily Attendance Summary",
    "Workforce Salary Coverage Board",
    "Biometric ID Audit",
    "Employee Data Gaps",
    "Workforce Anomaly Radar",
    "Workforce Payroll Readiness",
    # Promoted from DB-backed Query Reports. Script Reports reload from their
    # standard app JSON, which converges existing custom Query Report metadata.
    "Workforce Payroll Register",
    "Workforce Leave Balance Board",
    "Workforce Daily Attendance Board",
    "Workforce Shift Coverage",
    "Workforce Joiners and Leavers",
    "Workforce Pay Component Register",
    "Workforce Payroll Variance",
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
                if doc.module not in (None, "", "Workforce Suite"):
                    frappe.throw(
                        f"Cannot repair standard report {report_name!r} owned by module {doc.module!r}"
                    )
                frappe.delete_doc("Report", report_name, force=True, ignore_permissions=True)
        # Always reload the app-owned JSON so role-table changes self-heal on
        # existing standard reports without converting them to custom reports.
        frappe.reload_doc("workforce_suite", "report", frappe.scrub(report_name), force=True)
        # The standard report JSON is the source of filter defaults. Legacy
        # company-specific JavaScript rewriting is no longer needed.

# TXUX-260930-013 / P01: exact-name allowlist of app-owned UI artifacts proven
# unused by the accepted reference audit and re-audited read-only against
# staging before retirement. Source retirement is independent of database
# deletion: the installer no longer creates these records, and ordinary
# migration never deletes them. Deletion is a separate, explicit, idempotent
# operation that re-checks live references and unchanged app ownership first
# (see ``remove_retired_dashboard_artifacts``).
#
# Only canonical generic artifacts remain in the product allowlist.
# Existing customer-specific prototypes are left untouched by normal migrations.
# Generic installations only own these eleven canonical retired UI artifacts.
# Historic aliases are not product-level deletion targets.
RETIRED_NUMBER_CARDS = (
    "Workforce Active Employees",
    "Workforce Punches Logged",
    "Workforce Present Records",
    "Workforce Absent Records",
)

RETIRED_DASHBOARD_CHARTS = (
    "Workforce Employees by Department",
    "Workforce Employees by Branch",
    "Workforce Headcount by Company",
    "Workforce Attendance Status",
    "Workforce Leave Allocated by Type",
    "Workforce Payroll by Month",
    "Workforce Checkins by Day",
)


RETIRED_ARTIFACTS = (
    ("Number Card", RETIRED_NUMBER_CARDS),
    ("Dashboard Chart", RETIRED_DASHBOARD_CHARTS),
)


CANONICAL_RETIRED_ARTIFACTS = (
    ("Number Card", (
        "Workforce Active Employees",
        "Workforce Punches Logged",
        "Workforce Present Records",
        "Workforce Absent Records",
    )),
    ("Dashboard Chart", (
        "Workforce Employees by Department",
        "Workforce Employees by Branch",
        "Workforce Headcount by Company",
        "Workforce Attendance Status",
        "Workforce Leave Allocated by Type",
        "Workforce Payroll by Month",
        "Workforce Checkins by Day",
    )),
)
CANONICAL_DELETABLE_ARTIFACTS = frozenset(
    (dt, name)
    for dt, names in CANONICAL_RETIRED_ARTIFACTS
    for name in names
)


# The exact original installer payloads of the eleven canonical artifacts,
# kept only as unchanged-ownership fingerprints. They are never used to create
# records; a deletion candidate must still match every field below, including
# presentation-relevant properties and native defaults, so a record that was
# customized after the app created it is retained. Historical aliases and
# prototype duplicates have no reliable fingerprint and are always retained
# rather than guessed.
RETIRED_ARTIFACT_FINGERPRINTS = {
    ("Number Card", "Workforce Active Employees"): {
        "label": "Active Employees (All Companies)", "type": "Document Type",
        "document_type": "Employee", "function": "Count",
        "filters_json": json.dumps([["Employee", "status", "=", "Active", False]]),
        "dynamic_filters_json": None, "filters_config": None,
        "aggregate_function_based_on": None, "parent_document_type": None,
        "report_name": None, "report_field": None, "method": None,
        "is_standard": 0, "is_public": 1, "color": "Green",
        "background_color": None, "show_percentage_stats": 1, "stats_time_interval": "Daily",
        "show_full_number": 0, "report_function": "Sum", "currency": "BDT",
    },
    ("Number Card", "Workforce Punches Logged"): {
        "label": "Total Punches Logged", "type": "Document Type",
        "document_type": "Employee Checkin", "function": "Count",
        "filters_json": json.dumps([["Employee Checkin", "docstatus", "<", "2", False]]),
        "dynamic_filters_json": None, "filters_config": None,
        "aggregate_function_based_on": None, "parent_document_type": None,
        "report_name": None, "report_field": None, "method": None,
        "is_standard": 0, "is_public": 1, "color": "Blue",
        "background_color": None, "show_percentage_stats": 1, "stats_time_interval": "Daily",
        "show_full_number": 0, "report_function": "Sum", "currency": "BDT",
    },
    ("Number Card", "Workforce Present Records"): {
        "label": "Attendance Present Logs", "type": "Document Type",
        "document_type": "Attendance", "function": "Count",
        "filters_json": json.dumps([["Attendance", "status", "=", "Present", False]]),
        "dynamic_filters_json": None, "filters_config": None,
        "aggregate_function_based_on": None, "parent_document_type": None,
        "report_name": None, "report_field": None, "method": None,
        "is_standard": 0, "is_public": 1, "color": "Cyan",
        "background_color": None, "show_percentage_stats": 1, "stats_time_interval": "Daily",
        "show_full_number": 0, "report_function": "Sum", "currency": "BDT",
    },
    ("Number Card", "Workforce Absent Records"): {
        "label": "Attendance Absent Logs", "type": "Document Type",
        "document_type": "Attendance", "function": "Count",
        "filters_json": json.dumps([["Attendance", "status", "=", "Absent", False]]),
        "dynamic_filters_json": None, "filters_config": None,
        "aggregate_function_based_on": None, "parent_document_type": None,
        "report_name": None, "report_field": None, "method": None,
        "is_standard": 0, "is_public": 1, "color": "Red",
        "background_color": None, "show_percentage_stats": 1, "stats_time_interval": "Daily",
        "show_full_number": 0, "report_function": "Sum", "currency": "BDT",
    },
    ("Dashboard Chart", "Workforce Employees by Department"): {
        "chart_name": "Workforce Employees by Department",
        "chart_type": "Group By", "document_type": "Employee", "group_by_type": "Count",
        "group_by_based_on": "department", "type": "Bar",
        "filters_json": json.dumps([["Employee", "status", "=", "Active", False]]),
        "is_standard": 0, "is_public": 1, "show_values_over_chart": 0,
        "custom_options": None, "dynamic_filters_json": None, "color": None,
        "time_interval": "Yearly", "timespan": "Last Year", "timeseries": 0,
    },
    ("Dashboard Chart", "Workforce Employees by Branch"): {
        "chart_name": "Workforce Employees by Branch",
        "chart_type": "Group By", "document_type": "Employee", "group_by_type": "Count",
        "group_by_based_on": "branch", "type": "Bar",
        "filters_json": json.dumps([["Employee", "status", "=", "Active", False]]),
        "is_standard": 0, "is_public": 1, "show_values_over_chart": 0,
        "custom_options": None, "dynamic_filters_json": None, "color": None,
        "time_interval": "Yearly", "timespan": "Last Year", "timeseries": 0,
        "currency": "BDT",
    },
    ("Dashboard Chart", "Workforce Headcount by Company"): {
        "chart_name": "Workforce Headcount by Company",
        "chart_type": "Group By", "document_type": "Employee", "group_by_type": "Count",
        "group_by_based_on": "company", "type": "Pie",
        "filters_json": json.dumps([["Employee", "status", "=", "Active", False]]),
        "is_standard": 0, "is_public": 1, "show_values_over_chart": 0,
        "custom_options": None, "dynamic_filters_json": None, "color": None,
        "time_interval": "Yearly", "timespan": "Last Year", "timeseries": 0,
        "currency": "BDT",
    },
    ("Dashboard Chart", "Workforce Attendance Status"): {
        "chart_name": "Workforce Attendance Status",
        "chart_type": "Group By", "document_type": "Attendance", "group_by_type": "Count",
        "group_by_based_on": "status", "type": "Pie", "filters_json": json.dumps([]),
        "is_standard": 0, "is_public": 1, "show_values_over_chart": 0,
        "custom_options": None, "dynamic_filters_json": None, "color": None,
        "time_interval": "Yearly", "timespan": "Last Year", "timeseries": 0,
        "currency": "BDT",
    },
    ("Dashboard Chart", "Workforce Leave Allocated by Type"): {
        "chart_name": "Workforce Leave Allocated by Type",
        "chart_type": "Group By", "document_type": "Leave Allocation", "group_by_type": "Sum",
        "group_by_based_on": "leave_type", "aggregate_function_based_on": "total_leaves_allocated",
        "type": "Bar", "filters_json": json.dumps([]), "is_standard": 0, "is_public": 1,
        "show_values_over_chart": 0, "custom_options": None, "dynamic_filters_json": None, "color": None,
        "time_interval": "Yearly", "timespan": "Last Year", "timeseries": 0,
    },
    ("Dashboard Chart", "Workforce Payroll by Month"): {
        "chart_name": "Workforce Payroll by Month",
        "chart_type": "Sum", "document_type": "Salary Slip", "based_on": "start_date",
        "value_based_on": "net_pay", "timeseries": 1, "timespan": "Last Year",
        "time_interval": "Monthly", "type": "Line",
        "filters_json": json.dumps([["Salary Slip", "docstatus", "=", "1", False]]),
        "is_standard": 0, "is_public": 1, "show_values_over_chart": 0,
        "custom_options": None, "dynamic_filters_json": None, "color": None,
        "currency": "BDT",
    },
    ("Dashboard Chart", "Workforce Checkins by Day"): {
        "chart_name": "Workforce Checkins by Day",
        "chart_type": "Count", "document_type": "Employee Checkin", "based_on": "time",
        "timeseries": 1, "timespan": "Last Month", "time_interval": "Daily", "type": "Line",
        "filters_json": json.dumps([["Employee Checkin", "docstatus", "<", "2", False]]),
        "is_standard": 0, "is_public": 1, "show_values_over_chart": 0,
        "custom_options": None, "dynamic_filters_json": None, "color": None,
    },
}


# Functional reference surfaces inspected before any deletion. Private
# Workspaces live in the same ``tabWorkspace`` table as public ones, so the
# content/child-table checks cover both. Historical Version/UI Version rows are
# deliberately not checked: they are audit history, not live references.
# Similarly, ``link_type`` columns store target doctype/category names rather
# than artifact names and are excluded.
RETIRED_ARTIFACT_REFERENCE_SURFACES = (
    ("tabWorkspace Chart", "chart_name"),
    ("tabWorkspace Number Card", "number_card_name"),
    ("tabWorkspace Shortcut", "link_to"),
    ("tabWorkspace Link", "link_to"),
    ("tabWorkspace", "content"),
    ("tabDashboard Chart Link", "chart"),
    ("tabNumber Card Link", "card"),
    ("tabCustom HTML Block", "html"),
    ("tabCustom HTML Block", "script"),
    ("tabCustom HTML Block", "style"),
    ("tabDesktop Icon", "link_to"),
    ("tabDesktop Icon", "link"),
    ("tabWorkspace Sidebar Item", "link_to"),
    ("tabWorkspace Sidebar Item", "url"),
    ("tabWorkspace Sidebar Item", "route_options"),
    ("tabWorkspace Sidebar Item", "filters"),
    ("__UserSettings", "data"),
)

_OWNED_ARTIFACT_MODULE = "Workforce Suite"


WORKSPACE_SHORTCUTS = [
    ("Today's Attendance", "Workforce Daily Attendance Board", "Report"),
    ("Attendance Summary", "Daily Attendance Summary", "Report"),
    ("Mobile Attendance", "workforce-mobile-attendance", "Page"),
    ("Live Locations", "workforce-live-locations", "Page"),
    ("Punch Log", "Employee Checkin", "DocType"),
    ("Attendance Records", "Attendance", "DocType"),
    ("Employee Directory", "Employee", "DocType"),
    ("Departments", "Department", "DocType"),
    ("Designations", "Designation", "DocType"),
    ("Branches / Locations", "Branch", "DocType"),
    ("Joiners & Leavers", "Workforce Joiners and Leavers", "Report"),
    ("Employee Transfers", "Employee Transfer", "DocType"),
    ("Exits / Separations", "Employee Separation", "DocType"),
    ("Final Settlements", "Full and Final Statement", "DocType"),
    ("Run Monthly Payroll", "Workforce Payroll Readiness", "Report"),
    ("Payroll Entries (Advanced)", "Payroll Entry", "DocType"),
    ("Salary Slips", "Salary Slip", "DocType"),
    ("Salary Structures", "Salary Structure", "DocType"),
    ("Salary Assignments", "Salary Structure Assignment", "DocType"),
    ("Salary Components", "Salary Component", "DocType"),
    ("Extra Pay & Deductions", "Additional Salary", "DocType"),
    ("Payroll Register", "Workforce Payroll Register", "Report"),
    ("Payroll Variance", "Workforce Payroll Variance", "Report"),
    ("Pay Component Register", "Workforce Pay Component Register", "Report"),
    ("Salary Setup Coverage", "Workforce Salary Coverage Board", "Report"),
    ("Payroll Rules", "Workforce Payroll Policy", "DocType"),
    ("Policy Exceptions", "Workforce Policy Exception", "DocType"),
    ("Leave Requests", "Leave Application", "DocType"),
    ("Leave Allocations", "Leave Allocation", "DocType"),
    ("Leave Balances", "Workforce Leave Balance Board", "Report"),
    ("Shift Types", "Shift Type", "DocType"),
    ("Shift Planner", "Shift Schedule", "DocType"),
    ("Shift Assignments", "Shift Assignment", "DocType"),
    ("Shift Coverage", "Workforce Shift Coverage", "Report"),
    ("Attendance Policies", "Workforce Attendance Policy", "DocType"),
    ("Field Duties", "Workforce Field Duty", "DocType"),
    ("Location Pings", "Workforce Location Ping", "DocType"),
    ("Anomaly Radar", "Workforce Anomaly Radar", "Report"),
    ("Missing Employee Data", "Employee Data Gaps", "Report"),
    ("Biometric ID Audit", "Biometric ID Audit", "Report"),
    ("Biometric Devices", "Workforce Biometric Device", "DocType"),
    ("Employee Biometric IDs", "Workforce Employee Biometric", "DocType"),
    ("Face Match Settings", "Workforce Face Match Settings", "DocType"),
    ("Bulk Data Import", "Data Import", "DocType"),
    ("Employee Promotions", "Employee Promotion", "DocType"),
    ("Job Openings", "Job Opening", "DocType"),
    ("Job Applicants", "Job Applicant", "DocType"),
    ("Job Offers", "Job Offer", "DocType"),
    ("Onboarding", "Employee Onboarding", "DocType"),
    ("Overtime Reviews", "Overtime Slip", "DocType"),
    ("Leave Policies", "Leave Policy", "DocType"),
    ("Leave Policy Assignments", "Leave Policy Assignment", "DocType"),
    ("Leave Periods", "Leave Period", "DocType"),
    ("Holiday Lists", "Holiday List", "DocType"),
    ("Payroll Corrections", "Payroll Correction", "DocType"),
    ("Salary Arrears", "Arrear", "DocType"),
    ("Wage Floor Reviews", "Workforce Wage Floor Classification", "DocType"),
    ("Benefit Enrollments", "Workforce Statutory Benefit Enrollment", "DocType"),
    ("Working Time Reviews", "Workforce Working Time Classification", "DocType"),
    ("Maternity Reviews", "Workforce Maternity Review", "DocType"),
    ("Welfare Reviews", "Workforce Workplace Welfare Review", "DocType"),
    ("Statutory Form Layouts", "Workforce Statutory Print Layout", "DocType"),
    ("Statutory Evidence Records", "Workforce Statutory Record", "DocType"),
    ("Statutory Exit Rules", "Workforce Statutory Rule Set", "DocType"),
    ("Wage Floor Rules", "Workforce Wage Floor Rule Set", "DocType"),
    ("Benefit Rules", "Workforce Statutory Benefit Rule Set", "DocType"),
    ("Working Time Rules", "Workforce Working Time Rule Set", "DocType"),
    ("Maternity Rules", "Workforce Maternity Rule Set", "DocType"),
    ("Income Tax Slabs", "Income Tax Slab", "DocType"),
    ("Payroll Periods", "Payroll Period", "DocType"),
    # Expenses & Travel
    ("Expense Claims", "Expense Claim", "DocType"),
    ("Employee Advances", "Employee Advance", "DocType"),
    ("Travel Requests", "Travel Request", "DocType"),
    ("Employee Advance Summary", "Employee Advance Summary", "Report"),
    ("Unpaid Expense Claims", "Unpaid Expense Claim", "Report"),
    ("Expense Claim Types", "Expense Claim Type", "DocType"),
    ("Purpose of Travel", "Purpose of Travel", "DocType"),
    # Leave & Holidays
    ("Compensatory Leave Requests", "Compensatory Leave Request", "DocType"),
    ("Leave Encashment", "Leave Encashment", "DocType"),
    ("Holiday List Assignments", "Holiday List Assignment", "DocType"),
    ("Leave Types", "Leave Type", "DocType"),
    ("Leave Block Lists", "Leave Block List", "DocType"),
    # Attendance & Shifts
    ("Shift Requests", "Shift Request", "DocType"),
    ("Shift Schedule Assignments", "Shift Schedule Assignment", "DocType"),
    ("Shift Locations", "Shift Location", "DocType"),
    ("Overtime Types", "Overtime Type", "DocType"),
    ("Attendance Periods", "Workforce Attendance Period", "DocType"),
    ("Monthly Attendance Sheet", "Monthly Attendance Sheet", "Report"),
    ("Shift Attendance", "Shift Attendance", "Report"),
    ("Employees Working on a Holiday", "Employees working on a holiday", "Report"),
    # Payroll
    ("Employee Incentive", "Employee Incentive", "DocType"),
    ("Retention Bonus", "Retention Bonus", "DocType"),
    ("Salary Withholding", "Salary Withholding", "DocType"),
    # Recruitment
    ("Staffing Plans", "Staffing Plan", "DocType"),
    ("Job Requisitions", "Job Requisition", "DocType"),
    ("Interviews", "Interview", "DocType"),
    ("Interview Feedback", "Interview Feedback", "DocType"),
    ("Employee Referrals", "Employee Referral", "DocType"),
    ("Appointment Letters", "Appointment Letter", "DocType"),
    ("Interview Types", "Interview Type", "DocType"),
    ("Appointment Letter Templates", "Appointment Letter Template", "DocType"),
    ("Recruitment Analytics", "Recruitment Analytics", "Report"),
    # Development & Relations
    ("Employee Grievances", "Employee Grievance", "DocType"),
    ("Training Programs", "Training Program", "DocType"),
    ("Training Events", "Training Event", "DocType"),
    ("Appraisals", "Appraisal", "DocType"),
    ("Goals", "Goal", "DocType"),
    ("Employee Skill Map", "Employee Skill Map", "DocType"),
    ("Training Feedback", "Training Feedback", "DocType"),
    ("Training Results", "Training Result", "DocType"),
    ("Appraisal Cycles", "Appraisal Cycle", "DocType"),
    ("Grievance Types", "Grievance Type", "DocType"),
    ("Appraisal Templates", "Appraisal Template", "DocType"),
    # Setup
    ("Employee Grades", "Employee Grade", "DocType"),
    ("Employee Groups", "Employee Group", "DocType"),
    ("HR Settings", "HR Settings", "DocType"),
    ("Payroll Settings", "Payroll Settings", "DocType"),
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
    "Attendance Periods": "calendar",
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
    "Employee Promotions": "change",
    "Job Openings": "hr",
    "Job Applicants": "users",
    "Job Offers": "clipboard",
    "Onboarding": "users",
    "Overtime Reviews": "calendar",
    "Leave Policies": "setting-gear",
    "Leave Policy Assignments": "assign",
    "Leave Periods": "calendar",
    "Holiday Lists": "calendar",
    "Payroll Corrections": "change",
    "Salary Arrears": "money-coins-1",
    "Wage Floor Reviews": "clipboard",
    "Benefit Enrollments": "users",
    "Working Time Reviews": "calendar",
    "Maternity Reviews": "clipboard",
    "Welfare Reviews": "clipboard",
    "Statutory Exit Rules": "setting-gear",
    "Wage Floor Rules": "setting-gear",
    "Benefit Rules": "setting-gear",
    "Working Time Rules": "setting-gear",
    "Maternity Rules": "setting-gear",
    "Income Tax Slabs": "setting-gear",
    "Payroll Periods": "calendar",
    # New icons
    "Expense Claims": "money-coins-1",
    "Employee Advances": "money-coins-1",
    "Travel Requests": "map",
    "Employee Advance Summary": "list-alt",
    "Unpaid Expense Claims": "list-alt",
    "Expense Claim Types": "setting-gear",
    "Purpose of Travel": "setting-gear",
    "Compensatory Leave Requests": "clipboard",
    "Leave Encashment": "money-coins-1",
    "Holiday List Assignments": "assign",
    "Leave Types": "setting-gear",
    "Leave Block Lists": "setting-gear",
    "Shift Requests": "clipboard",
    "Shift Schedule Assignments": "assign",
    "Shift Locations": "location",
    "Overtime Types": "setting-gear",
    "Monthly Attendance Sheet": "calendar",
    "Shift Attendance": "calendar",
    "Employees Working on a Holiday": "calendar",
    "Employee Incentive": "money-coins-1",
    "Retention Bonus": "money-coins-1",
    "Salary Withholding": "money-coins-1",
    "Staffing Plans": "users",
    "Job Requisitions": "clipboard",
    "Interviews": "users",
    "Interview Feedback": "clipboard",
    "Employee Referrals": "users",
    "Appointment Letters": "file",
    "Interview Types": "setting-gear",
    "Appointment Letter Templates": "setting-gear",
    "Recruitment Analytics": "chart",
    "Employee Grievances": "solid-warning",
    "Training Programs": "hr",
    "Training Events": "calendar",
    "Appraisals": "clipboard",
    "Goals": "check",
    "Employee Skill Map": "users",
    "Training Feedback": "clipboard",
    "Training Results": "list-alt",
    "Appraisal Cycles": "calendar",
    "Grievance Types": "setting-gear",
    "Appraisal Templates": "setting-gear",
    "Employee Grades": "setting-gear",
    "Employee Groups": "users",
    "HR Settings": "setting-gear",
    "Payroll Settings": "setting-gear",
}

WORKSPACE_SECTIONS = (
    ("Employees", "Maintain identity and use native records for employment changes.", (
        "Employee Directory", "Joiners & Leavers", "Employee Transfers", "Employee Promotions", "Missing Employee Data",
    )),
    ("Attendance & Shifts", "Review work evidence, attendance requests, and shift coverage.", (
        "Today's Attendance", "Attendance Summary", "Attendance Fix Requests", "Attendance Records", "Punch Log",
        "Mobile Attendance", "Field Duties", "Overtime Reviews", "Attendance Periods",
        "Shift Assignments", "Bulk Shift Assignment", "Shift Requests", "Shift Schedule Assignments", "Shift Planner", "Shift Coverage",
        "Shift Locations", "Overtime Types",
        "Monthly Attendance Sheet", "Shift Attendance", "Employees Working on a Holiday",
    )),
    ("Leave & Holidays", "Review requests and explicitly configured leave entitlements.", (
        "Leave Requests", "Compensatory Leave Requests", "Leave Balances", "Leave Allocations", "Bulk Leave Allocation",
        "Leave Encashment",
        "Leave Policy Assignments", "Holiday List Assignments", "Holiday Lists", "Leave Types", "Leave Policies", "Leave Periods", "Leave Block Lists",
    )),
    ("Expenses & Travel", "Submit and review native employee expenses, advances and travel.", (
        "Expense Claims", "Employee Advances", "Travel Requests",
        "Employee Advance Summary", "Unpaid Expense Claims",
        "Expense Claim Types", "Purpose of Travel",
    )),
    ("Payroll", "Prepare and review native salary authority and payroll.", (
        "Run Monthly Payroll", "Salary Setup Coverage", "Bulk Salary Structure Assignment", "Salary Assignments",
        "Payroll Entries (Advanced)", "Salary Slips", "Extra Pay & Deductions", "Payroll Corrections", "Salary Arrears",
        "Employee Incentive", "Retention Bonus", "Salary Withholding",
    )),
    ("Recruitment", "Move reviewed hires through native recruitment and onboarding.", (
        "Staffing Plans", "Job Requisitions", "Job Openings", "Job Applicants", "Interviews", "Interview Feedback",
        "Employee Referrals", "Job Offers", "Appointment Letters", "Onboarding",
        "Interview Types", "Appointment Letter Templates", "Recruitment Analytics",
    )),
    ("Development & Relations", "Manage employee grievances, training events and appraisals.", (
        "Employee Grievances", "Training Programs", "Training Events", "Appraisals", "Goals", "Employee Skill Map",
        "Training Feedback", "Training Results", "Appraisal Cycles",
        "Grievance Types", "Appraisal Templates",
    )),
    ("Separation", "Review operational exit and settlement separately.", (
        "Exits / Separations", "Final Settlements",
    )),
    ("Compliance", "Review explicit applicability without inventing legal values.", (
        "Wage Floor Reviews", "Benefit Enrollments", "Working Time Reviews", "Maternity Reviews", "Welfare Reviews",
        "Statutory Form Layouts", "Statutory Evidence Records",
    )),
    ("Reports", "Open the reviews allowed for your role and scope.", (
        "Anomaly Radar", "Payroll Register", "Payroll Variance", "Pay Component Register", "Biometric ID Audit",
    )),
    ("Setup", "Reviewed configuration for authorized administrators.", (
        "Departments", "Designations", "Branches / Locations", "Employee Grades", "Employee Groups",
        "HR Settings", "Payroll Settings",
        "Shift Types", "Attendance Policies",
        "Salary Structures", "Salary Components", "Payroll Rules", "Income Tax Slabs", "Payroll Periods",
        "Statutory Exit Rules", "Wage Floor Rules", "Benefit Rules", "Working Time Rules", "Maternity Rules",
        "Policy Exceptions", "Bulk Data Import",
    )),
    ("Devices", "Device and field evidence for authorized support roles.", (
        "Biometric Devices", "Employee Biometric IDs", "Face Match Settings", "Live Locations", "Location Pings",
    )),
)

# Home is an operator starting point; the full catalog below remains in Sidebar.
# TXUX-260930-013 removed the snapshot cards; the Workspace keeps zero cards.

# Expense drafts have no Action Board category and are useful for resuming work.
HOME_QUICK_LISTS = [
    {
        "document_type": "Expense Claim",
        "label": "Draft Expense Claims",
        "quick_list_filter": json.dumps({"docstatus": 0, "approval_status": "Draft"}),
    },
]

COMMON_ACTION_SHORTCUTS = [
    "Employee Directory",
    "Today's Attendance",
    "Attendance Fix Requests",
    "Leave Requests",
    "Expense Claims",
    "Run Monthly Payroll",
    "Job Applicants",
    "Final Settlements",
]


def workspace_sidebar_items(shortcuts):
    """Native metadata only: Frappe filters every target for the current user."""
    available = {label: (target, kind) for label, target, kind in shortcuts}
    items = [{"label": "Home / Action Board", "type": "Link", "link_type": "Workspace",
              "link_to": "workforce-suite", "icon": "home", "child": 0}]
    for title, _description, labels in WORKSPACE_SECTIONS:
        selected = [label for label in labels if label in available]
        if not selected:
            continue
        items.append({"label": title, "type": "Section Break", "collapsible": 1, "keep_closed": 1})
        for label in selected:
            target, kind = available[label]
            items.append({"label": label, "type": "Link", "link_type": kind, "link_to": target,
                          "child": 1, "icon": WORKSPACE_SHORTCUT_ICONS.get(label)})
    return items


# Persistent native field help has no shared or per-user completion state.
ATTENDANCE_REQUEST_GUIDANCE = (
    "Explain the dates and why this request is needed. Save a draft for an "
    "authorized independent reviewer to submit. A draft does not create "
    "approved Attendance."
)


def ensure_operator_guidance():
    """Create native contextual help; preserve administrator-owned overrides."""
    filters = {"doc_type": "Attendance Request", "field_name": "explanation", "property": "description"}
    if not frappe.db.exists("Property Setter", filters):
        from frappe.custom.doctype.property_setter.property_setter import make_property_setter
        make_property_setter("Attendance Request", "explanation", "description",
                             ATTENDANCE_REQUEST_GUIDANCE, "Small Text")


def ensure_workspace_sidebar(shortcuts):
    name = "Workforce Suite"
    doc = frappe.get_doc("Workspace Sidebar", name) if frappe.db.exists("Workspace Sidebar", name) else frappe.new_doc("Workspace Sidebar")
    doc.title = name
    doc.module = "Workforce Suite"
    doc.app = "workforce_suite"
    doc.standard = 0  # Source-owned installer metadata; no developer-mode export.
    doc.for_user = None
    doc.header_icon = "users"
    doc.set("items", workspace_sidebar_items(shortcuts))
    doc.save(ignore_permissions=True)



WORKSPACE_NAMES = {
    "workforce-suite": {"title": "Workforce Suite", "module": "Workforce Suite"},
}
LEGACY_WORKSPACE_NAMES = (
    # The prototype also created a title-named copy. Keep only the canonical
    # slug workspace so Desk has one unambiguous HR entry point.
    "Workforce Suite",
    "workforce-hr",
        "workforce-hr-management",
)
CANONICAL_WORKSPACE_NAME = "workforce-suite"


def workspace_is_visible(name: str) -> bool:
    """Keep one managed HR workspace in Desk navigation."""
    return name == CANONICAL_WORKSPACE_NAME


def workspace_blocks(shortcuts=None):
    """Return the native-first home layout with progressive disclosure."""
    shortcuts = shortcuts if shortcuts is not None else list(WORKSPACE_SHORTCUTS) + list(BULK_WORKSPACE_SHORTCUTS)
    available = {row[0]: row for row in shortcuts}
    blocks = [
        {"type": "header", "data": {"text": "<h2>Workforce Suite Action Board</h2>", "col": 12}},
        {"type": "custom_block", "data": {"custom_block_name": "Workforce Work Needing Attention", "col": 12}},
    ]
    for ql in HOME_QUICK_LISTS:
        blocks.append({
            "type": "quick_list",
            "data": {"quick_list_name": ql["label"], "col": 12},
        })
    blocks.append({"type": "header", "data": {"text": "<h3>Frequent Actions</h3>", "col": 12}})
    for label in COMMON_ACTION_SHORTCUTS:
        if label in available:
            blocks.append({
                "type": "shortcut",
                "data": {"shortcut_name": label, "col": 3},
            })
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
            if doc.module not in (None, "", "Workforce Suite"):
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
            "is_standard": config.get("is_standard", "No"), "module": "Workforce Suite",
            "query": config.get("query"), "report_script": config.get("report_script"),
            "javascript": config["javascript"], "disabled": 0,
        }
        if "roles" in config:
            values["roles"] = config["roles"]
        _ensure_custom_report(values)


def _raw_table_exists(table: str) -> bool:
    return bool(frappe.db.sql(
        "select 1 from information_schema.tables where table_schema=database() and table_name=%s",
        (table,),
    ))


def _column_exists(table: str, column: str) -> bool:
    return bool(frappe.db.sql(
        "select 1 from information_schema.columns where table_schema=database() and table_name=%s and column_name=%s",
        (table, column),
    ))


def _custom_reference_surfaces() -> list[tuple[str, str]]:
    """Discover custom fields linking to Dashboard Chart or Number Card.

    Fails closed (raises RuntimeError) if an unresolvable custom Dynamic Link field
    is detected, ensuring candidates are retained.
    """
    if not _raw_table_exists("tabCustom Field"):
        return []

    unresolvable = frappe.db.sql(
        """
        select dt, fieldname from `tabCustom Field`
        where fieldtype = 'Dynamic Link'
        """,
        as_dict=True,
    )
    if unresolvable:
        field_desc = ", ".join(f"{r.dt}.{r.fieldname}" for r in unresolvable)
        raise RuntimeError(
            f"Unresolvable custom Dynamic Link field(s) present ({field_desc}); cannot exclude references"
        )

    custom_links = frappe.db.sql(
        """
        select dt, fieldname from `tabCustom Field`
        where fieldtype = 'Link' and options in ('Dashboard Chart', 'Number Card')
        """,
        as_dict=True,
    )
    surfaces = []
    for row in custom_links:
        table = f"tab{row.dt}"
        surfaces.append((table, row.fieldname))
    return surfaces


def _functional_reference_count(artifact_name: str) -> int:
    """Count live references to an artifact across supported surfaces.

    Inspects native tables/columns and dynamically discovers custom Link fields
    targeting Dashboard Chart or Number Card. If an unresolvable custom Dynamic Link
    exists or any surface query fails, raises an exception so the caller fails closed
    and retains the candidate.

    Non-reference fields (e.g. `link_type` containing DocType names rather than artifact
    names, or historical `tabVersion` rows containing audit history) are deliberately
    excluded.
    """
    total = 0
    all_surfaces = list(RETIRED_ARTIFACT_REFERENCE_SURFACES) + _custom_reference_surfaces()
    for table, column in all_surfaces:
        if not _raw_table_exists(table):
            continue
        if not _column_exists(table, column):
            continue
        rows = frappe.db.sql(
            f"select count(*) from `{table}` where `{column}` like %s",
            (f"%{artifact_name}%",),
        )
        total += int((rows[0][0] if rows else 0) or 0)
    return total


def _artifact_ownership_mismatch(doctype: str, name: str, expected: dict) -> str | None:
    """Return why a record no longer matches its original app definition."""
    doc = frappe.db.get_value(doctype, name, list(expected) + ["module"], as_dict=True)
    if not doc:
        return "record no longer exists"
    if (doc.get("module") or "") != _OWNED_ARTIFACT_MODULE:
        return f"module is {doc.get('module')!r}, not {_OWNED_ARTIFACT_MODULE!r}"
    for field, expected_value in expected.items():
        current = doc.get(field)
        if field in ("filters_json", "dynamic_filters_json"):
            try:
                same = frappe.parse_json(current or "[]") == frappe.parse_json(expected_value or "[]")
            except Exception:
                same = False
        elif isinstance(expected_value, int):
            same = frappe.utils.cint(current) == expected_value
        elif expected_value is None:
            same = current is None or (isinstance(current, str) and not current.strip())
        else:
            same = (current or "") == expected_value
        if not same:
            return f"{field!r} differs from the retired app definition"
    return None


def _candidate_disposition(
    doctype: str,
    name: str,
    fingerprints: dict,
    *,
    allow_non_canonical: bool = False,
) -> tuple[str, str]:
    """Classify one deletion candidate: absent, removable, or retained + why."""
    if not frappe.db.exists(doctype, name):
        return "absent", ""
    if not allow_non_canonical and (doctype, name) not in CANONICAL_DELETABLE_ARTIFACTS:
        return "retained", "historical alias; non-deletable without separately established app ownership"
    expected = fingerprints.get((doctype, name))
    if not expected:
        return "retained", "no unchanged-ownership fingerprint; retained instead of guessing"
    mismatch = _artifact_ownership_mismatch(doctype, name, expected)
    if mismatch:
        return "retained", f"ownership/customization check failed: {mismatch}"
    try:
        references = _functional_reference_count(name)
    except Exception as exc:
        return "retained", f"reference surfaces could not be inspected ({exc}); retained"
    if references:
        return "retained", f"{references} functional reference(s) still exist"
    return "removable", ""


def _plan_retired_artifacts_internal(
    candidates,
    fingerprints,
    *,
    allow_non_canonical: bool = False,
) -> dict:
    removable: list[dict] = []
    retained: list[dict] = []
    for doctype, names in candidates:
        for name in names:
            disposition, reason = _candidate_disposition(
                doctype, name, fingerprints, allow_non_canonical=allow_non_canonical
            )
            if disposition == "removable":
                removable.append({"doctype": doctype, "name": name})
            elif disposition == "retained":
                retained.append({"doctype": doctype, "name": name, "reason": reason})
    return {"dry_run": True, "removable": removable, "retained": retained}


def plan_retired_dashboard_artifacts() -> dict:
    """Non-destructive cleanup plan for production; never deletes anything.

    Inspects the canonical retired artifacts and historical aliases against
    all functional reference surfaces and unchanged app ownership fingerprints.
    """
    return _plan_retired_artifacts_internal(
        candidates=RETIRED_ARTIFACTS,
        fingerprints=RETIRED_ARTIFACT_FINGERPRINTS,
        allow_non_canonical=False,
    )


def _backup_directory() -> Path:
    return Path(frappe.get_site_path("private", "backups"))


def verify_backup_preflight(backup_reference: str, backup_checksum: str | None = None) -> Path:
    """Verify that an operator-provided backup reference exists, matches site database format, matches checksum, and has valid archive integrity.

    An arbitrary string is merely an operator reference, not proof of a restorable backup.
    This preflight verifies:
    1. The reference is a pure filename without path traversal.
    2. The filename matches Frappe's supported site-specific full database backup convention:
       <YYYYMMDD_HHMMSS>-<site_slug>-database.sql.gz (rejecting partial backups, .txt, .tar, file archives, or foreign-site files).
    3. The backup archive exists in the site's private/backups directory and is non-empty.
    4. A verified SHA-256 checksum from BACKUPS.md is supplied and matches the archive's SHA-256.
    5. Gzip stream integrity and CRC32 trailer are valid across the entire archive.

    Operational Boundary:
    Passing this preflight proves the archive exists, conforms to the database backup naming
    format for the active site, matches the given SHA-256, and is an uncorrupted gzip stream.
    It does NOT prove that the database SQL dump inside is semantically restorable or that
    the backup is current. The operator must independently verify that the checksum appears
    in a fresh, site-specific BACKUPS.md entry recorded immediately prior to cleanup, and
    that complete database recovery procedures have been rehearsed and proven.

    Throws frappe.ValidationError if any check fails.
    """
    ref = (backup_reference or "").strip()
    if not ref:
        frappe.throw(
            "An operator-provided backup reference from BACKUPS.md is required before removing retired artifacts.",
            frappe.ValidationError,
        )

    ref_path = Path(ref)
    if ref_path.name != ref or "/" in ref or "\\" in ref:
        frappe.throw(
            f"Backup reference {ref!r} must be a pure filename, not a path.",
            frappe.ValidationError,
        )

    site = (frappe.local.site or "").strip()
    if not site:
        frappe.throw("Active Frappe site identity is not set.", frappe.ValidationError)

    site_tag = site.replace(".", "_")
    db_backup_pattern = re.compile(
        rf"^\d{{8}}_\d{{6}}-(?:{re.escape(site_tag)}|{re.escape(site)})-database\.sql\.gz$"
    )
    if not db_backup_pattern.match(ref):
        frappe.throw(
            f"Backup reference {ref!r} is not a supported full database backup archive (.sql.gz) for site {site!r}. "
            f"Expected format: <YYYYMMDD_HHMMSS>-{site_tag}-database.sql.gz",
            frappe.ValidationError,
        )

    backup_file = _backup_directory() / ref
    if not backup_file.is_file() or backup_file.stat().st_size == 0:
        frappe.throw(
            f"Backup archive {ref!r} does not exist or is empty in {backup_file.parent}.",
            frappe.ValidationError,
        )

    chk = (backup_checksum or "").strip().lower()
    if not chk:
        frappe.throw(
            f"A verified SHA-256 checksum from BACKUPS.md is required to confirm integrity for backup {ref!r}.",
            frappe.ValidationError,
        )

    hasher = hashlib.sha256()
    with backup_file.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    actual_chk = hasher.hexdigest().lower()

    if actual_chk != chk:
        frappe.throw(
            f"Backup checksum verification failed for {ref!r}: expected {chk}, actual {actual_chk}.",
            frappe.ValidationError,
        )

    try:
        with gzip.open(backup_file, "rb") as gz:
            for _ in iter(lambda: gz.read(65536), b""):
                pass
    except Exception as exc:
        frappe.throw(
            f"Backup archive {ref!r} failed gzip integrity validation ({exc}).",
            frappe.ValidationError,
        )

    return backup_file


def _remove_retired_artifacts_internal(
    apply: bool = False,
    backup_reference: str | None = None,
    backup_checksum: str | None = None,
    candidates=None,
    fingerprints=None,
    *,
    allow_non_canonical: bool = False,
) -> dict:
    candidates = candidates if candidates is not None else RETIRED_ARTIFACTS
    fingerprints = fingerprints if fingerprints is not None else RETIRED_ARTIFACT_FINGERPRINTS
    plan = _plan_retired_artifacts_internal(
        candidates, fingerprints, allow_non_canonical=allow_non_canonical
    )
    result = {"applied": False, **plan}
    if not apply:
        return result
    _require_cleanup_operator()
    verify_backup_preflight(backup_reference or "", backup_checksum)

    removed: list[dict] = []
    retained = list(plan["retained"])
    for item in plan["removable"]:
        if not allow_non_canonical and (item["doctype"], item["name"]) not in CANONICAL_DELETABLE_ARTIFACTS:
            retained.append({
                "doctype": item["doctype"],
                "name": item["name"],
                "reason": "candidate is outside the canonical eleven allowlist; non-deletable in production",
            })
            continue
        # Never trust a stale plan: re-verify immediately before deleting.
        disposition, reason = _candidate_disposition(
            item["doctype"], item["name"], fingerprints, allow_non_canonical=allow_non_canonical
        )
        if disposition == "removable":
            frappe.delete_doc(item["doctype"], item["name"], force=True, ignore_permissions=True)
            removed.append(item)
        elif disposition == "retained":
            retained.append({"doctype": item["doctype"], "name": item["name"], "reason": reason})
    return {
        "applied": True,
        "backup_reference": backup_reference,
        "backup_checksum": (backup_checksum or "").lower(),
        "removed": removed,
        "retained": retained,
    }


def remove_retired_dashboard_artifacts(
    apply: bool = False,
    backup_reference: str | None = None,
    backup_checksum: str | None = None,
) -> dict:
    """Explicit, idempotent retired-artifact cleanup; dry-run by default.

    Ordinary migration never calls this. Applying deletions is a deliberate
    deployment-checkpoint action: it requires a named System Manager (or
    Administrator) session and an independently verified backup reference and
    SHA-256 checksum recorded in ``BACKUPS.md``, for example::

        bench --site <site> execute workforce_suite.install.remove_retired_dashboard_artifacts
        bench --site <site> execute workforce_suite.install.remove_retired_dashboard_artifacts \\
            --kwargs "{'apply': True, 'backup_reference': 'YOUR_VERIFIED-database.sql.gz', 'backup_checksum': 'YOUR_VERIFIED_SHA256'}"

    Every candidate is re-checked for live references and unchanged app
    ownership immediately before deletion; anything referenced, customized or
    uninspectable is retained and reported. Idempotent: a second execution is
    harmless.
    """
    return _remove_retired_artifacts_internal(
        apply=apply,
        backup_reference=backup_reference,
        backup_checksum=backup_checksum,
        candidates=RETIRED_ARTIFACTS,
        fingerprints=RETIRED_ARTIFACT_FINGERPRINTS,
        allow_non_canonical=False,
    )


def _plan_retired_dashboard_artifacts_for_tests(candidates, fingerprints) -> dict:
    """Test injection facility for dry-run planning with synthetic fixtures."""
    return _plan_retired_artifacts_internal(candidates, fingerprints, allow_non_canonical=True)


def _remove_retired_dashboard_artifacts_for_tests(
    apply: bool = False,
    backup_reference: str | None = None,
    backup_checksum: str | None = None,
    candidates=None,
    fingerprints=None,
) -> dict:
    """Test injection facility for cleanup execution with synthetic fixtures."""
    return _remove_retired_artifacts_internal(
        apply=apply,
        backup_reference=backup_reference,
        backup_checksum=backup_checksum,
        candidates=candidates,
        fingerprints=fingerprints,
        allow_non_canonical=True,
    )


def _require_cleanup_operator() -> None:
    if frappe.session.user == "Administrator":
        return
    if "System Manager" in set(frappe.get_roles()):
        return
    frappe.throw("Only a System Manager can remove retired artifacts.", frappe.PermissionError)


def rename_legacy_reports() -> None:
    """Compatibility no-op. Historical source names belong to legacy migration."""
    return



def ensure_action_board_block() -> None:
    from pathlib import Path
    from workforce_suite.workforce_suite.action_board import BOARD_ROLES

    name = "Workforce Work Needing Attention"
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
    from workforce_suite.workforce_suite.action_board import BOARD_ROLES

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
    if not frappe.db.exists("DocType", "Workforce Biometric Device"):
        shortcuts = [row for row in shortcuts if row[1] != "Workforce Biometric Device"]
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

        # This cross-module home is role-gated, not gated on having a custom
        # app DocType permission. Native HR-only approvers need their home too.
        doc.module = None
        doc.app = "workforce_suite"
        doc.set("roles", [{"role": role} for role in sorted(BOARD_ROLES)])
        doc.content = content
        doc.type = "Workspace"
        doc.title = workspace_values["title"]
        doc.public = 1 if workspace_is_visible(name) else 0
        doc.is_hidden = 0 if workspace_is_visible(name) else 1
        doc.charts = []
        doc.number_cards = []
        doc.quick_lists = []
        for ql in HOME_QUICK_LISTS:
            if frappe.db.exists("DocType", ql["document_type"]):
                doc.append("quick_lists", {
                    "document_type": ql["document_type"],
                    "label": ql["label"],
                    "quick_list_filter": ql["quick_list_filter"],
                })
        doc.set("custom_blocks", [{"custom_block_name": "Workforce Work Needing Attention", "label": "Workforce Work Needing Attention"}])
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
    # Validate the Home Link only after fresh-install Workspace creation.
    ensure_operator_guidance()
    ensure_workspace_sidebar(shortcuts)


def ensure_owned_desktop_logo() -> int:
    """Repair only the app-owned legacy packaged logo URL.

    Native Desktop Icon remains the source of truth. Customer or other-app
    logos are left untouched, and the operation is idempotent.
    """
    old_logo = "/assets/tradex_hr/images/tradex-hr.svg"
    new_logo = "/assets/workforce_suite/images/workforce-hr.svg"
    changed = 0
    for name in frappe.get_all("Desktop Icon", filters={"app": "workforce_suite"}, pluck="name"):
        doc = frappe.get_doc("Desktop Icon", name)
        if doc.logo_url != old_logo:
            continue
        doc.logo_url = new_logo
        doc.flags.ignore_permissions = True
        doc.save()
        changed += 1
    return changed


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
    from workforce_suite.branch_setup import ensure_branch_fields
    from workforce_suite.role_setup import ensure_workforce_roles
    from workforce_suite.approval_setup import ensure_workforce_workflows
    from workforce_suite.field_attendance_setup import ensure_field_attendance_fields
    from workforce_suite.field_financial_setup import (
        ensure_income_tax_review_fields,
        ensure_payroll_adjustment_workflow_fields,
    )
    from workforce_suite.field_employee_exit_setup import ensure_default_exit_template, ensure_employee_exit_fields
    from workforce_suite.field_working_time_setup import ensure_working_time_holiday_category_field

    ensure_branch_fields()
    ensure_workforce_roles()
    ensure_payroll_adjustment_workflow_fields()
    ensure_employee_exit_fields()
    ensure_workforce_workflows()
    ensure_default_exit_template()
    ensure_field_attendance_fields()
    # Salary Components are company/configuration decisions, not install defaults.
    ensure_working_time_holiday_category_field()
    ensure_income_tax_review_fields()
    # Historic structure pay-basis seeding is an explicit reviewed migration
    # utility, not a generic install action on another company's structures.
    ensure_reports()
    # TXUX-260930-013-P01: retired artifacts are never recreated here, and
    # ordinary migration never deletes them. Removal is a separate explicit,
    # backed-up checkpoint action: remove_retired_dashboard_artifacts(apply=True,
    # backup_reference=...). See that function's docstring.
    rename_legacy_reports()
    ensure_workspace()
    ensure_owned_desktop_logo()
    ensure_property_setters()
    frappe.db.commit()
    frappe.clear_cache()
