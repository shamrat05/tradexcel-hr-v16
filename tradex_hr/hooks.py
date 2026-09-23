app_name = "tradex_hr"
app_title = "Tradexcel HR"
app_publisher = "Tradexcel"
# Describes what the app *is*, not its migration history. It previously said
# "integration for SelevoHR and SenseFace devices" — Selevo is the retired
# system, and the app is the HR system now, not an integration to it.
app_description = "Configurable Tradexcel HRMS for Tradexcel Ceramics Ltd. and Elegance Footwear Ltd."
# Was the placeholder admin@tradex.com, which is also the address the retired
# Selevo used. Kept as a real support mailbox rather than a non-existent domain.
app_email = "hr@tradexcel.com"
app_license = "MIT"

app_include_css = ["tradex_hr.bundle.css"]
app_include_js = ["tradex_hr.bundle.js"]

# A DB-backed Query Report interpolates its SQL with the filter dict directly, so
# a missing placeholder raises from the database driver before MariaDB sees the
# query. This override fills the unambiguous ones for the app's own reports and
# delegates to Frappe unchanged for everything else. Frappe's supported
# extension point -- no core files are modified.
override_whitelisted_methods = {
    "frappe.desk.query_report.run": "tradex_hr.report_filters.run",
}

add_to_apps_screen = [{
    "name": "tradex_hr",
    "logo": "/assets/tradex_hr/images/tradex-hr.svg",
    "title": "Tradexcel HR",
    "route": "/app/tradexcel-hr",
}]

doctype_js = {
    "Tradexcel Biometric Device": "public/js/tradexcel_biometric_device.js",
    "Employee": "public/js/employee_calendar.js",
    "Attendance": "public/js/employee_calendar.js",
    "Income Tax Slab": "public/js/income_tax_slab.js",
}

doctype_list_js = {
    "Employee": "public/js/list_scope.js",
    "Attendance": "public/js/list_scope.js",
    "Employee Checkin": "public/js/list_scope.js",
    "Salary Slip": "public/js/list_scope.js",
    "Leave Application": "public/js/list_scope.js",
    "Salary Structure Assignment": "public/js/list_scope.js",
    "Leave Allocation": "public/js/list_scope.js",
    "Additional Salary": "public/js/list_scope.js",
    "Payroll Entry": "public/js/list_scope.js",
}

doc_events = {
    "Income Tax Slab": {
        "validate": "tradex_hr.tradexcel_hr.tax_review.validate_income_tax_slab_review",
    },
    "Payroll Entry": {
        "before_submit": "tradex_hr.tradexcel_hr.native_payroll.validate_payroll_entry_before_submit",
        # A submitted Payroll Entry workflow transition uses save()'s
        # before_update_after_submit event; validate() is not run by Frappe in
        # that lifecycle, so enforce the gate at the native transition hook.
        "before_update_after_submit": "tradex_hr.tradexcel_hr.financial_readiness.validate_payroll_financial_readiness_before_approval",
    },
    "Salary Slip": {
        "before_submit": "tradex_hr.tradexcel_hr.native_payroll.validate_salary_slip_before_submit",
        "before_validate": "tradex_hr.tradexcel_hr.component_exceptions.apply_to_salary_slip",
    },
    "Attendance": {
        "before_save": "tradex_hr.tradexcel_hr.attendance_exceptions.apply_to_attendance",
        "validate": "tradex_hr.tradexcel_hr.attendance_exceptions.sync_scope_fields",
    },
    "Employee Checkin": {
        "before_validate": "tradex_hr.tradexcel_hr.field_attendance_service.enrich_mobile_checkin",
    },
}

after_install = "tradex_hr.install.after_install"
after_migrate = "tradex_hr.install.after_migrate"


has_permission = {
    "Salary Slip": "tradex_hr.tradexcel_hr.native_payroll.restrict_salary_slip_delete",
}
