app_name = "tradex_hr"
app_title = "Tradexcel HR"
app_publisher = "Tradexcel"
app_description = "Configurable Tradexcel HRMS integration for SelevoHR and SenseFace devices"
app_email = "admin@tradex.com"
app_license = "MIT"

add_to_apps_screen = [{
    "name": "tradex_hr",
    "logo": "/assets/tradex_hr/images/tradex-hr.svg",
    "title": "Tradexcel HR",
    "route": "/app/tradexcel-hr",
}]

doctype_js = {
    "Tradexcel Biometric Device": "public/js/tradexcel_biometric_device.js",
    "Employee": "public/js/employee_calendar.js",
}

doc_events = {
    "Salary Slip": {
        "before_validate": [
            "tradex_hr.tradexcel_hr.component_exceptions.apply_to_salary_slip",
            "tradex_hr.tradexcel_hr.tax_exceptions.apply_tax_exemption",
        ],
    },
    "Attendance": {
        "before_save": "tradex_hr.tradexcel_hr.attendance_exceptions.apply_to_attendance",
    },
}

after_install = "tradex_hr.install.after_install"
after_migrate = "tradex_hr.install.after_migrate"
