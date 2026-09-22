"""Install-time reports and the Tradexcel HR action-board workspace."""

from __future__ import annotations

import json

import frappe


COMPANY = "Tradexcel Ceramics Ltd."
USER_COMPANY_DEFAULT_JS = '(frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || ""'
# Query Reports execute raw SQL and do not apply Employee/Company user-permission
# filters. Keep these cross-company reports global-admin-only until replaced by
# explicitly scoped Script Reports.
GLOBAL_REPORT_ROLES = ("System Manager",)

DAILY_ATTENDANCE_JAVASCRIPT = """
frappe.query_reports["Daily Attendance Summary"] = {
  filters: [
    {fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1},
    {fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1},
    {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "", reqd: 1},
    {fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch", default: "", get_query: function() { var c = frappe.query_report.get_filter_value('company'); return c ? {filters: {company: c}} : {}; }},
    {fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department", default: "", get_query: function() { var company = frappe.query_report.get_filter_value('company'); var branch = frappe.query_report.get_filter_value('branch'); if (!branch) { return company ? {filters: {company: company}} : {}; } return {query: 'tradex_hr.link_filters.departments_used_by_branch', filters: {company: company, branch: branch}}; }},
    {fieldname: "status", label: __("Status"), fieldtype: "Select", options: "\\nPresent\\nAbsent\\nOn Leave\\nHalf Day\\nHoliday\\nNot Started", default: ""}
  ]
};
"""

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

EMPLOYEE_DATA_GAPS_JAVASCRIPT = """
frappe.query_reports["Employee Data Gaps"] = {
  filters: [
    {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "", reqd: 1},
    {fieldname: "status", label: __("Employee Status"), fieldtype: "Select", options: "Active\\nInactive\\nLeft\\nAll", default: "Active"},
    {fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch", default: "", get_query: function() { var c = frappe.query_report.get_filter_value('company'); return c ? {filters: {company: c}} : {}; }},
    {fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department", default: "", get_query: function() { var company = frappe.query_report.get_filter_value('company'); var branch = frappe.query_report.get_filter_value('branch'); if (!branch) { return company ? {filters: {company: company}} : {}; } return {query: 'tradex_hr.link_filters.departments_used_by_branch', filters: {company: company, branch: branch}}; }},
    {fieldname: "employment_type", label: __("Employment Type"), fieldtype: "Select", options: "All\\nWorker\\nNon Worker", default: "All"},
    {fieldname: "gap_type", label: __("Gap"), fieldtype: "Select", options: "All\\nMissing Department\\nMissing Employee Number\\nNo Active Salary Assignment\\nMultiple Active Salary Assignments\\nLatest Structure Is a Wage Structure\\nWorker Without Wage Structure\\nFuture Joining Date With Punches\\nMissing Designation\\nMissing Date of Birth\\nMissing Holiday List", default: "All"},
    {fieldname: "priority", label: __("Priority"), fieldtype: "Select", options: "All\\nHigh\\nMedium\\nLow", default: "All"}
  ],
  onload: function(report) {
    report.page.add_inner_button(__("Open Employee List for Bulk Fix"), function() {
      frappe.route_options = {
        company: report.get_filter_value("company"),
        status: report.get_filter_value("status")
      };
      frappe.set_route("List", "Employee");
    });
    report.page.add_inner_button(__("Fill Missing Fields (Export / Upload)"), function() {
      frappe.msgprint({
        title: __("Employee data update"),
        message: __("In Data Import, download an Update Existing Records template, select only the fields you need, fill verified values, then upload and review the preview/errors before starting import. Leave unknown values blank; do not create employee users until their emails are verified."),
        indicator: "blue"
      });
      frappe.new_doc("Data Import", {
        reference_doctype: "Employee",
        import_type: "Update Existing Records"
      });
    });
  }
};
"""

WORKFORCE_ANOMALY_RADAR_JAVASCRIPT = """
frappe.query_reports["Workforce Anomaly Radar"] = {
  filters: [
    {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "", reqd: 1},
    {fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1},
    {fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1},
    {fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch", default: "", get_query: function() { var c = frappe.query_report.get_filter_value('company'); return c ? {filters: {company: c}} : {}; }},
    {fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department", default: "", get_query: function() { var company = frappe.query_report.get_filter_value('company'); var branch = frappe.query_report.get_filter_value('branch'); if (!branch) { return company ? {filters: {company: company}} : {}; } return {query: 'tradex_hr.link_filters.departments_used_by_branch', filters: {company: company, branch: branch}}; }},
    {fieldname: "category", label: __("Category"), fieldtype: "Select", options: "All\\nCheckin\\nAttendance\\nPayroll\\nLeave\\nTax", default: "All"},
    {fieldname: "severity", label: __("Severity"), fieldtype: "Select", options: "All\\nHigh\\nMedium\\nLow", default: "All"},
    {fieldname: "z_threshold", label: __("Outlier Z Threshold"), fieldtype: "Float", default: 3.5, description: __("Modified z-score cutoff for cohort outliers (standard practice: 3.5)")},
    {fieldname: "min_cohort", label: __("Minimum Cohort Size"), fieldtype: "Int", default: 5, description: __("Groups smaller than this are skipped so statistics stay meaningful")}
  ]
};
"""

REPORTS = {
    "Tradexcel Shift Coverage": {
        "ref_doctype": "Shift Assignment",
        "roles": GLOBAL_REPORT_ROLES,
        "query": """
WITH active_assignments AS (
    SELECT employee, COUNT(*) assignment_count,
           GROUP_CONCAT(DISTINCT shift_type ORDER BY shift_type SEPARATOR ', ') shifts,
           MIN(start_date) first_start, MAX(end_date) last_end
    FROM `tabShift Assignment`
    WHERE docstatus=1 AND start_date<=%(as_of_date)s
      AND (end_date IS NULL OR end_date>=%(as_of_date)s)
    GROUP BY employee
)
SELECT e.name AS "Employee:Link/Employee:120",
       e.employee_name AS "Employee Name:Data:180",
       e.company AS "Company:Link/Company:160",
       e.branch AS "Branch:Link/Branch:130",
       e.department AS "Department:Link/Department:150",
       COALESCE(a.assignment_count,0) AS "Assignments:Int:90",
       COALESCE(a.shifts,'') AS "Assigned Shifts:Data:170",
       COALESCE(e.default_shift,'') AS "Default Shift:Link/Shift Type:140",
       CASE WHEN a.assignment_count>1 THEN 'Overlap - review'
            WHEN a.assignment_count=1 THEN 'Assigned'
            WHEN e.default_shift IS NOT NULL AND e.default_shift<>'' THEN 'Default only'
            ELSE 'Missing - review' END AS "Coverage:Data:130"
FROM `tabEmployee` e
LEFT JOIN active_assignments a ON a.employee=e.name
WHERE e.company=%(company)s AND e.status='Active'
  AND (e.date_of_joining IS NULL OR e.date_of_joining<=%(as_of_date)s)
  AND (e.relieving_date IS NULL OR e.relieving_date>=%(as_of_date)s)
  AND (%(branch)s='' OR e.branch=%(branch)s)
  AND (%(department)s='' OR e.department=%(department)s)
  AND (%(coverage)s='All' OR
       (%(coverage)s='Overlap' AND a.assignment_count>1) OR
       (%(coverage)s='Assigned' AND a.assignment_count=1) OR
       (%(coverage)s='Missing' AND a.assignment_count IS NULL AND
        (e.default_shift IS NULL OR e.default_shift='')) OR
       (%(coverage)s='Default only' AND a.assignment_count IS NULL AND e.default_shift IS NOT NULL AND e.default_shift<>''))
ORDER BY CASE WHEN a.assignment_count>1 THEN 0
              WHEN a.assignment_count IS NULL AND (e.default_shift IS NULL OR e.default_shift='') THEN 1
              ELSE 2 END, e.branch, e.department, e.name
""",
        "javascript": """
frappe.query_reports["Tradexcel Shift Coverage"] = {filters: [
  {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "", reqd: 1},
  {fieldname: "as_of_date", label: __("As Of Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1},
  {fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch", default: ""},
  {fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department", default: ""},
  {fieldname: "coverage", label: __("Coverage"), fieldtype: "Select", options: "All\\nOverlap\\nMissing\\nAssigned\\nDefault only", default: "All"}
]};
""",
    },
    "Tradexcel Pay Component Register": {
        "ref_doctype": "Salary Slip",
        "roles": GLOBAL_REPORT_ROLES,
        "query": """
SELECT s.name AS "Salary Slip:Link/Salary Slip:150",
       s.employee AS "Employee:Link/Employee:120",
       s.employee_name AS "Employee Name:Data:180",
       e.branch AS "Branch:Link/Branch:130",
       e.department AS "Department:Link/Department:150",
       s.start_date AS "Period From:Date:100",
       s.end_date AS "Period To:Date:100",
       CASE WHEN d.parentfield='earnings' THEN 'Earning' ELSE 'Deduction' END AS "Type:Data:95",
       d.salary_component AS "Component:Link/Salary Component:180",
       d.amount AS "Amount:Currency:110",
       CASE WHEN s.docstatus=0 THEN 'Draft' ELSE 'Submitted' END AS "Slip Status:Data:90"
FROM `tabSalary Detail` d
JOIN `tabSalary Slip` s ON s.name=d.parent AND d.parenttype='Salary Slip'
JOIN `tabEmployee` e ON e.name=s.employee
WHERE s.company=%(company)s AND s.docstatus<2
  AND s.start_date>=%(from_date)s AND s.start_date<=%(to_date)s
  AND d.parentfield IN ('earnings', 'deductions')
  AND (%(branch)s='' OR e.branch=%(branch)s)
  AND (%(department)s='' OR e.department=%(department)s)
  AND (%(component)s='' OR d.salary_component=%(component)s)
  AND (%(component_type)s='All' OR
       (%(component_type)s='Earning' AND d.parentfield='earnings') OR
       (%(component_type)s='Deduction' AND d.parentfield='deductions'))
ORDER BY s.start_date, e.branch, e.department, s.employee, d.parentfield, d.idx
""",
        "javascript": """
frappe.query_reports["Tradexcel Pay Component Register"] = {filters: [
  {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "", reqd: 1},
  {fieldname: "from_date", label: __("Period From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1},
  {fieldname: "to_date", label: __("Period To"), fieldtype: "Date", default: frappe.datetime.month_end(), reqd: 1},
  {fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch", default: ""},
  {fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department", default: ""},
  {fieldname: "component_type", label: __("Type"), fieldtype: "Select", options: "All\\nEarning\\nDeduction", default: "All"},
  {fieldname: "component", label: __("Component"), fieldtype: "Link", options: "Salary Component", default: ""}
]};
""",
    },
    "Tradexcel Payroll Variance": {
        "ref_doctype": "Salary Slip",
        "roles": GLOBAL_REPORT_ROLES,
        "query": """
WITH current_pay AS (
    SELECT employee, MAX(employee_name) employee_name, MAX(company) company,
           COUNT(*) slips, SUM(gross_pay) gross, SUM(total_deduction) deductions,
           SUM(net_pay) net, SUM(docstatus=0) drafts, SUM(docstatus=1) submitted
    FROM `tabSalary Slip`
    WHERE company=%(company)s AND docstatus<2
      AND start_date>=%(from_date)s AND start_date<=%(to_date)s
    GROUP BY employee
), previous_pay AS (
    SELECT employee, SUM(net_pay) net
    FROM `tabSalary Slip`
    WHERE company=%(company)s AND docstatus<2
      AND start_date>=DATE_SUB(%(from_date)s, INTERVAL 1 MONTH)
      AND start_date<%(from_date)s
    GROUP BY employee
)
SELECT c.employee AS "Employee:Link/Employee:120",
       c.employee_name AS "Employee Name:Data:180",
       e.branch AS "Branch:Link/Branch:130",
       e.department AS "Department:Link/Department:150",
       c.slips AS "Slip Count:Int:90", c.drafts AS "Drafts:Int:75",
       c.submitted AS "Submitted:Int:90", c.gross AS "Gross:Currency:110",
       c.deductions AS "Deductions:Currency:110",
       c.net AS "Current Net:Currency:120",
       p.net AS "Previous Net:Currency:120",
       c.net-COALESCE(p.net,0) AS "Change:Currency:110",
       CASE WHEN c.net=0 THEN 'Zero pay - review'
            WHEN p.net IS NULL THEN 'No previous slip'
            WHEN c.slips>1 THEN 'Multiple slips - review'
            ELSE 'Compare' END AS "Review:Data:170"
FROM current_pay c
JOIN `tabEmployee` e ON e.name=c.employee
LEFT JOIN previous_pay p ON p.employee=c.employee
WHERE (%(branch)s='' OR e.branch=%(branch)s)
  AND (%(department)s='' OR e.department=%(department)s)
ORDER BY e.branch, e.department, c.employee
""",
        "javascript": """
frappe.query_reports["Tradexcel Payroll Variance"] = {filters: [
  {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "", reqd: 1},
  {fieldname: "from_date", label: __("Period From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1},
  {fieldname: "to_date", label: __("Period To"), fieldtype: "Date", default: frappe.datetime.month_end(), reqd: 1},
  {fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch", default: ""},
  {fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department", default: ""}
]};
""",
    },
    "Tradexcel Joiners and Leavers": {
        "ref_doctype": "Employee",
        "roles": GLOBAL_REPORT_ROLES,
        "query": """
SELECT e.name AS "Employee:Link/Employee:120",
       e.employee_name AS "Employee Name:Data:180",
       e.company AS "Company:Link/Company:160",
       e.branch AS "Branch:Link/Branch:130",
       e.department AS "Department:Link/Department:150",
       'Joined' AS "Movement:Data:90", e.date_of_joining AS "Date:Date:100"
FROM `tabEmployee` e
WHERE e.company=%(company)s AND e.date_of_joining BETWEEN %(from_date)s AND %(to_date)s
  AND (%(branch)s='' OR e.branch=%(branch)s)
UNION ALL
SELECT e.name, e.employee_name, e.company, e.branch, e.department,
       'Left', e.relieving_date
FROM `tabEmployee` e
WHERE e.company=%(company)s AND e.relieving_date BETWEEN %(from_date)s AND %(to_date)s
  AND (%(branch)s='' OR e.branch=%(branch)s)
ORDER BY 7, 6, 1
""",
        "javascript": """
frappe.query_reports["Tradexcel Joiners and Leavers"] = {filters: [
  {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "", reqd: 1},
  {fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1},
  {fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1},
  {fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch", default: ""}
]};
""",
    },
    "Tradexcel Daily Attendance Board": {
        "ref_doctype": "Attendance",
        "query": """
SELECT e.name AS \"Employee:Link/Employee:120\", e.employee_number AS \"Employee ID:Data:100\",
e.employee_name AS \"Employee Name:Data:180\", e.company AS \"Company:Link/Company:160\",
e.branch AS \"Branch:Link/Branch:130\", e.department AS \"Department:Link/Department:160\",
COALESCE(a.status, 'Absent') AS \"Status:Data:90\", a.in_time AS \"In Time:Datetime:140\",
a.out_time AS \"Out Time:Datetime:140\", COALESCE(a.late_entry, 0) AS \"Late:Check:60\",
COALESCE(a.early_exit, 0) AS \"Early Exit:Check:80\", COUNT(c.name) AS \"Punches:Int:70\"
FROM `tabEmployee` e
LEFT JOIN `tabAttendance` a ON a.employee=e.name AND a.attendance_date=%(attendance_date)s AND a.docstatus<2
LEFT JOIN `tabEmployee Checkin` c ON c.employee=e.name AND DATE(c.time)=%(attendance_date)s
WHERE e.company=%(company)s AND (e.status='Active' OR e.relieving_date >= %(attendance_date)s)
GROUP BY e.name, a.name ORDER BY e.branch, e.department, e.name
""",
        "javascript": """
frappe.query_reports[\"Tradexcel Daily Attendance Board\"] = {
  filters: [
    {fieldname: \"attendance_date\", label: __(\"Attendance Date\"), fieldtype: \"Date\", default: frappe.datetime.get_today(), reqd: 1},
    {fieldname: \"company\", label: __(\"Company\"), fieldtype: \"Link\", options: \"Company\", reqd: 1}
  ]
};
""",
    },
    "Tradexcel Payroll Register": {
        "ref_doctype": "Salary Slip",
        "query": """
SELECT s.name AS \"Salary Slip:Link/Salary Slip:140\", s.employee AS \"Employee:Link/Employee:120\",
s.employee_name AS \"Employee Name:Data:180\", s.company AS \"Company:Link/Company:160\",
s.start_date AS \"From Date:Date:90\", s.end_date AS \"To Date:Date:90\",
s.gross_pay AS \"Gross Pay:Currency:110\", s.total_deduction AS \"Deductions:Currency:110\",
s.net_pay AS \"Net Pay:Currency:110\", s.docstatus AS \"Status:Int:60\"
FROM `tabSalary Slip` s WHERE s.company=%(company)s AND s.start_date >= %(from_date)s
AND s.end_date <= %(to_date)s ORDER BY s.start_date, s.employee
""",
        "javascript": """
frappe.query_reports[\"Tradexcel Payroll Register\"] = {
  filters: [
    {fieldname: \"company\", label: __(\"Company\"), fieldtype: \"Link\", options: \"Company\", reqd: 1},
    {fieldname: \"from_date\", label: __(\"From Date\"), fieldtype: \"Date\", reqd: 1},
    {fieldname: \"to_date\", label: __(\"To Date\"), fieldtype: \"Date\", reqd: 1}
  ]
};
""",
    },
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
    "Tradexcel Leave Balance Board": {
        "ref_doctype": "Leave Allocation",
        "query": """
SELECT e.name AS \"Employee:Link/Employee:120\", e.employee_number AS \"Employee ID:Data:100\",
e.employee_name AS \"Employee Name:Data:180\", e.company AS \"Company:Link/Company:160\",
la.leave_type AS \"Leave Type:Link/Leave Type:150\", la.from_date AS \"From Date:Date:90\",
la.to_date AS \"To Date:Date:90\", la.new_leaves_allocated AS \"Allocated:Float:90\",
la.total_leaves_allocated AS \"Total Allocated:Float:100\"
FROM `tabLeave Allocation` la JOIN `tabEmployee` e ON e.name=la.employee
WHERE e.company=%(company)s AND la.from_date <= %(as_of_date)s AND la.to_date >= %(as_of_date)s
ORDER BY e.department, e.employee_name, la.leave_type
""",
        "javascript": """
frappe.query_reports[\"Tradexcel Leave Balance Board\"] = {
  filters: [
    {fieldname: \"company\", label: __(\"Company\"), fieldtype: \"Link\", options: \"Company\", reqd: 1},
    {fieldname: \"as_of_date\", label: __(\"As Of Date\"), fieldtype: \"Date\", default: frappe.datetime.get_today(), reqd: 1}
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
        "javascript": EMPLOYEE_DATA_GAPS_JAVASCRIPT,
    },
    "Workforce Anomaly Radar": {
        "ref_doctype": "Employee",
        "report_type": "Script Report",
        "is_standard": "Yes",
        "javascript": WORKFORCE_ANOMALY_RADAR_JAVASCRIPT,
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
)


def ensure_standard_script_reports() -> None:
    """Restore app-owned Python reports from their file-backed definitions.

    Frappe executes a standard Script Report through its app module. A custom
    Script Report instead executes ``report_script`` with safe_exec, which is
    disabled by default in v16. Older migrations demoted these five records;
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
        doc = frappe.get_doc("Report", report_name)
        javascript = doc.javascript or ""
        company_aware_javascript = javascript.replace(
            'default: "Tradexcel Ceramics Ltd."',
            f"default: {USER_COMPANY_DEFAULT_JS}",
        )
        if company_aware_javascript != javascript:
            doc.db_set("javascript", company_aware_javascript, update_modified=False)

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
    "Tradexcel TCL Active Employees": {
        "label": "TCL Active Employees",
        "type": "Document Type",
        "document_type": "Employee",
        "function": "Count",
        "filters_json": json.dumps([
            ["Employee", "company", "=", COMPANY, False],
            ["Employee", "status", "=", "Active", False],
        ]),
        "is_standard": 0,
        "module": "Tradexcel HR",
        "is_public": 1,
        "color": "Blue",
    },
    "Tradexcel EFL Active Employees": {
        "label": "EFL Active Employees",
        "type": "Document Type",
        "document_type": "Employee",
        "function": "Count",
        "filters_json": json.dumps([
            ["Employee", "company", "=", "Elegance Footwear Ltd.", False],
            ["Employee", "status", "=", "Active", False],
        ]),
        "is_standard": 0,
        "module": "Tradexcel HR",
        "is_public": 1,
        "color": "Purple",
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
    "TradeX TCL Active Employees": "Tradexcel TCL Active Employees",
    "TradeX EFL Active Employees": "Tradexcel EFL Active Employees",
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
    "TCL Active Employees",
    "TCL Active Employees-1",
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
    ("Run Monthly Payroll", "Payroll Entry", "DocType"),
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
    ("Bulk Salary Structure Assignment", "Salary Structure Assignment Tool", "DocType"),
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
        "Run Monthly Payroll", "Salary Slips", "Salary Structures", "Salary Assignments",
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
    blocks.extend(
        {"type": "number_card", "data": {"number_card_name": name, "col": 3}}
        for name in NUMBER_CARDS
    )
    blocks.extend([
        {"type": "header", "data": {"text": "<h3>Overview</h3>", "col": 12}},
    ])
    blocks.extend(
        {"type": "chart", "data": {"chart_name": name, "col": 6}}
        for name in DASHBOARD_CHARTS
    )
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


def ensure_daily_attendance_report() -> None:
    values = {
        "report_name": "Daily Attendance Summary",
        "ref_doctype": "Attendance",
        "report_type": "Script Report",
        "is_standard": "Yes",
        "module": "Tradexcel HR",
        "query": None,
        "report_script": None,
        "javascript": DAILY_ATTENDANCE_JAVASCRIPT,
        "disabled": 0,
    }
    _ensure_custom_report(values)


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

def ensure_workspace() -> None:
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
        doc.title = workspace_values["title"]
        doc.public = 1 if workspace_is_visible(name) else 0
        doc.is_hidden = 0 if workspace_is_visible(name) else 1
        doc.charts = []
        for chart_name in DASHBOARD_CHARTS:
            if frappe.db.exists("Dashboard Chart", chart_name):
                doc.append("charts", {"chart_name": chart_name, "label": chart_name})
        doc.number_cards = []
        for card_name in NUMBER_CARDS:
            if frappe.db.exists("Number Card", card_name):
                doc.append("number_cards", {"number_card_name": card_name, "label": card_name})
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
    from tradex_hr.branch_setup import ensure_branch_hierarchy
    from tradex_hr.role_setup import ensure_tradex_roles
    from tradex_hr.approval_setup import ensure_tradex_workflows
    from tradex_hr.field_attendance_setup import ensure_field_attendance_fields, ensure_field_transport_component
    from tradex_hr.tradexcel_hr.salary_setup import ensure_pay_basis_metadata

    ensure_branch_hierarchy()
    ensure_tradex_roles()
    ensure_tradex_workflows()
    ensure_field_attendance_fields()
    ensure_field_transport_component()
    # Persist explicit financial pay basis on existing native structures. This
    # does not infer from Employment Type and does not rewrite earnings rows.
    ensure_pay_basis_metadata(commit=False)
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
