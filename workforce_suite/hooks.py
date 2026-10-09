app_name = "workforce_suite"
app_title = "Workforce Suite"
app_publisher = "Workforce"
app_description = "Configurable, native-first HRMS workflows and controls"
# Use a genuine vendor support contact before distributing this app.
app_email = ""
app_license = "MIT"

app_include_css = ["workforce_suite.bundle.css"]
app_include_js = ["workforce_suite.bundle.js", "report_actions.bundle.js", "native_announcements.bundle.js"]
extend_bootinfo = "workforce_suite.navigation.extend_bootinfo"

add_to_apps_screen = [{
    "name": "workforce_suite",
    "logo": "/assets/workforce_suite/images/workforce-hr.svg",
    "title": "Workforce Suite",
    "route": "/app/workforce-suite",
}]

extend_doctype_class = {
    "Employee Transfer": [
        "workforce_suite.workforce_suite.employee_lifecycle.EmployeeTransferLifecycleMixin",
    ],
    "Employee Promotion": [
        "workforce_suite.workforce_suite.employee_lifecycle.EmployeePromotionLifecycleMixin",
    ],
    "Payroll Entry": [
        "workforce_suite.workforce_suite.payroll_finalization.PayrollEntryFinalizationMixin",
    ],
    "Payroll Correction": [
        "workforce_suite.workforce_suite.payroll_adjustments.PayrollCorrectionMixin",
    ],
    "Arrear": [
        "workforce_suite.workforce_suite.payroll_adjustments.WorkforceArrearMixin",
    ],
    "Full and Final Statement": [
        "workforce_suite.workforce_suite.employee_separation.FullAndFinalWorkforceMixin",
    ],
    "Shift Assignment Tool": [
        "workforce_suite.workforce_suite.shift_assignment_tool.WorkforceShiftAssignmentToolMixin",
    ],
    "Leave Control Panel": [
        "workforce_suite.workforce_suite.leave_control_panel.WorkforceLeaveControlPanelMixin",
    ],
    "Bulk Salary Structure Assignment": [
        "workforce_suite.workforce_suite.bulk_salary_structure_assignment.WorkforceBulkSalaryStructureAssignmentMixin",
    ],
}

doctype_js = {
    "Employee Checkin": "public/js/employee_checkin_review.js",
    "Workforce Biometric Device": "public/js/workforce_biometric_device.js",
    "Payroll Entry": "public/js/payroll_entry.js",
    "Salary Slip": "public/js/salary_slip_adjustments.js",
    "Employee": "public/js/employee_calendar.js",
    "Employee Separation": "public/js/employee_separation.js",
    "Attendance": "public/js/employee_calendar.js",
    "Shift Assignment Tool": "public/js/shift_assignment_tool.js",
    "Bulk Salary Structure Assignment": "public/js/bulk_salary_structure_assignment.js",
    "Income Tax Slab": "public/js/income_tax_slab.js",
    "Workforce Attendance Period": "public/js/workforce_attendance_period.js",
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
    "Overtime Slip": "public/js/overtime_bulk_list.js",
}

doc_events = {
    "Salary Structure": {
        "validate": "workforce_suite.workforce_suite.salary_structure_validation.validate_salary_structure",
    },
    "Leave Policy Assignment": {
        "before_submit": "workforce_suite.workforce_suite.leave_control_panel.require_submitted_leave_policy",
    },
    "Income Tax Slab": {
        "validate": "workforce_suite.workforce_suite.tax_review.validate_income_tax_slab_review",
    },
    "Payroll Correction": {
        "before_insert": "workforce_suite.workforce_suite.payroll_adjustments.initialize_adjustment_state",
        "validate": "workforce_suite.workforce_suite.payroll_adjustments.validate_payroll_correction",
        "before_save": "workforce_suite.workforce_suite.payroll_adjustments.validate_adjustment_before_save",
        "before_submit": "workforce_suite.workforce_suite.payroll_adjustments.validate_adjustment_before_submit",
        "before_cancel": "workforce_suite.workforce_suite.payroll_adjustments.validate_adjustment_before_cancel",
    },
    "Arrear": {
        "before_insert": "workforce_suite.workforce_suite.payroll_adjustments.initialize_adjustment_state",
        "validate": "workforce_suite.workforce_suite.payroll_adjustments.validate_arrear",
        "before_save": "workforce_suite.workforce_suite.payroll_adjustments.validate_adjustment_before_save",
        "before_submit": "workforce_suite.workforce_suite.payroll_adjustments.validate_adjustment_before_submit",
        "before_cancel": "workforce_suite.workforce_suite.payroll_adjustments.validate_adjustment_before_cancel",
    },
    "Additional Salary": {
        "before_submit": "workforce_suite.workforce_suite.working_time_compliance.validate_overtime_generated_additional_salary",
        "before_cancel": "workforce_suite.workforce_suite.payroll_adjustments.validate_additional_salary_before_cancel",
    },
    "Payroll Entry": {
        "before_submit": "workforce_suite.workforce_suite.native_payroll.validate_payroll_entry_before_submit",
        # A submitted Payroll Entry workflow transition uses save()'s
        # before_update_after_submit event; validate() is not run by Frappe in
        # that lifecycle, so enforce the gate at the native transition hook.
        "before_update_after_submit": "workforce_suite.workforce_suite.financial_readiness.validate_payroll_financial_readiness_before_approval",
    },
    "Salary Slip": {
        "before_submit": [
            "workforce_suite.workforce_suite.native_payroll.validate_salary_slip_before_submit",
            "workforce_suite.workforce_suite.maternity_welfare.validate_maternity_salary_slip",
        ],
        "before_validate": "workforce_suite.workforce_suite.component_exceptions.apply_to_salary_slip",
    },
    "Attendance": {
        "before_save": "workforce_suite.workforce_suite.attendance_exceptions.apply_to_attendance",
        "validate": "workforce_suite.workforce_suite.attendance_exceptions.sync_scope_fields",
        "before_submit": [
            "workforce_suite.workforce_suite.employee_separation.validate_no_payable_work_after_relieving_date",
            "workforce_suite.workforce_suite.maternity_welfare.validate_maternity_attendance",
        ],
    },
    "Attendance Request": {
        "validate": "workforce_suite.workforce_suite.employee_separation.validate_no_payable_work_after_relieving_date",
        "before_submit": "workforce_suite.workforce_suite.attendance_corrections.validate_attendance_request_before_submit",
        "before_cancel": "workforce_suite.workforce_suite.attendance_corrections.validate_attendance_request_before_cancel",
    },
    "Overtime Slip": {
        "validate": "workforce_suite.workforce_suite.employee_separation.validate_no_payable_work_after_relieving_date",
        "before_submit": [
            "workforce_suite.workforce_suite.working_time_compliance.validate_overtime_slip_before_submit",
            "workforce_suite.workforce_suite.maternity_welfare.validate_maternity_overtime",
        ],
        "before_cancel": "workforce_suite.workforce_suite.overtime_bulk.prevent_consumed_overtime_cancel",
    },
    "Workforce Field Duty": {
        "validate": [
            "workforce_suite.workforce_suite.employee_separation.validate_no_payable_work_after_relieving_date",
            "workforce_suite.workforce_suite.maternity_welfare.validate_maternity_field_duty",
        ],
    },
    "Employee Separation": {
        "validate": "workforce_suite.workforce_suite.employee_separation.validate_employee_separation",
        "before_submit": "workforce_suite.workforce_suite.maternity_welfare.validate_maternity_employee_separation",
    },
    "Employee Transfer": {
        "validate": "workforce_suite.workforce_suite.employee_lifecycle.validate_employee_transfer",
    },
    "Employee Promotion": {
        "validate": "workforce_suite.workforce_suite.employee_lifecycle.validate_employee_promotion",
    },
    "Full and Final Statement": {
        "before_submit": [
            "workforce_suite.workforce_suite.employee_separation.validate_full_and_final_before_submit",
            "workforce_suite.workforce_suite.maternity_welfare.validate_maternity_full_and_final",
        ],
    },
    "Workforce Maternity Rule Set": {
        "validate": "workforce_suite.workforce_suite.maternity_welfare.validate_maternity_rule_set",
        "before_submit": "workforce_suite.workforce_suite.maternity_welfare.validate_maternity_rule_submit",
        "before_update_after_submit": "workforce_suite.workforce_suite.maternity_welfare.before_update_after_submit_maternity_rule",
        "before_cancel": "workforce_suite.workforce_suite.maternity_welfare.prevent_maternity_rule_cancel",
    },
    "Workforce Maternity Review": {
        "validate": "workforce_suite.workforce_suite.maternity_welfare.validate_maternity_review",
        "before_submit": "workforce_suite.workforce_suite.maternity_welfare.before_submit_maternity_review",
        "before_update_after_submit": "workforce_suite.workforce_suite.maternity_welfare.before_update_after_submit_maternity_review",
        "before_cancel": "workforce_suite.workforce_suite.maternity_welfare.before_cancel_maternity_review",
    },
    "Workforce Maternity Separation Review": {
        "validate": "workforce_suite.workforce_suite.maternity_welfare.validate_maternity_separation_review",
        "before_submit": "workforce_suite.workforce_suite.maternity_welfare.before_submit_maternity_separation_review",
        "before_update_after_submit": "workforce_suite.workforce_suite.maternity_welfare.before_update_after_submit_maternity_separation_review",
        "before_cancel": "workforce_suite.workforce_suite.maternity_welfare.before_cancel_maternity_separation_review",
    },
    "Workforce Workplace Welfare Review": {
        "validate": "workforce_suite.workforce_suite.maternity_welfare.validate_workplace_welfare_review",
        "before_submit": "workforce_suite.workforce_suite.maternity_welfare.before_submit_workplace_welfare_review",
        "before_update_after_submit": "workforce_suite.workforce_suite.maternity_welfare.before_update_after_submit_workplace_welfare_review",
        "before_cancel": "workforce_suite.workforce_suite.maternity_welfare.before_cancel_workplace_welfare_review",
    },
    "Workforce Statutory Rule Set": {
        "validate": "workforce_suite.workforce_suite.statutory_exit.validate_statutory_ruleset",
        "before_submit": "workforce_suite.workforce_suite.statutory_exit.before_submit_statutory_ruleset",
        "before_update_after_submit": "workforce_suite.workforce_suite.statutory_exit.before_update_after_submit_statutory_ruleset",
        "before_cancel": "workforce_suite.workforce_suite.statutory_exit.before_cancel_statutory_ruleset",
    },
    "Employee Onboarding": {
        "validate": "workforce_suite.workforce_suite.joiner_readiness.validate_employee_onboarding",
    },
    "Job Opening": {
        "validate": "workforce_suite.workforce_suite.joiner_readiness.validate_recruitment_company_scope",
    },
    "Job Applicant": {
        "validate": "workforce_suite.workforce_suite.joiner_readiness.validate_recruitment_company_scope",
    },
    "Job Offer": {
        "validate": "workforce_suite.workforce_suite.joiner_readiness.validate_recruitment_company_scope",
    },
    "Interview": {
        "validate": "workforce_suite.workforce_suite.joiner_readiness.validate_recruitment_company_scope",
    },
    "Interview Feedback": {
        "validate": "workforce_suite.workforce_suite.joiner_readiness.validate_recruitment_company_scope",
    },
    "Employee": {
        "before_insert": "workforce_suite.workforce_suite.joiner_readiness.validate_unique_employee_job_applicant",
        "validate": [
            "workforce_suite.workforce_suite.employee_lifecycle.validate_employee_lifecycle_fields",
            "workforce_suite.workforce_suite.employee_lifecycle.validate_employee_employment_spell",
        ],
    },
    "Salary Structure Assignment": {
        "validate": "workforce_suite.workforce_suite.employee_lifecycle.validate_salary_structure_assignment",
        "before_submit": "workforce_suite.workforce_suite.employee_lifecycle.validate_salary_structure_assignment_before_submit",
        "before_cancel": "workforce_suite.workforce_suite.employee_lifecycle.validate_salary_structure_assignment_before_cancel",
    },
    "Employee Checkin": {
        "before_validate": "workforce_suite.workforce_suite.field_attendance_service.enrich_mobile_checkin",
    },
}

after_install = "workforce_suite.install.after_install"
after_migrate = "workforce_suite.install.after_migrate"


permission_query_conditions = {
    "Workforce Mobile Event": "workforce_suite.workforce_suite.report_scope.employee_link_query_conditions",
    "Leave Policy Assignment": "workforce_suite.workforce_suite.report_scope.employee_link_query_conditions",
    "Leave Application": "workforce_suite.workforce_suite.report_scope.employee_link_query_conditions",
    "Full and Final Statement": "workforce_suite.workforce_suite.report_scope.employee_link_query_conditions",
    "Workforce Field Duty": "workforce_suite.workforce_suite.report_scope.employee_link_query_conditions",
    "Workforce Location Ping": "workforce_suite.workforce_suite.report_scope.employee_link_query_conditions",

    "Payroll Entry": "workforce_suite.workforce_suite.report_scope.payroll_entry_query_conditions",
    "Shift Assignment": "workforce_suite.workforce_suite.report_scope.employee_link_query_conditions",
    "Shift Schedule Assignment": "workforce_suite.workforce_suite.report_scope.employee_link_query_conditions",
    "Shift Request": "workforce_suite.workforce_suite.report_scope.employee_link_query_conditions",
    "Leave Allocation": "workforce_suite.workforce_suite.report_scope.employee_link_query_conditions",
    "Additional Salary": "workforce_suite.workforce_suite.report_scope.employee_link_query_conditions",
    "Overtime Slip": "workforce_suite.workforce_suite.report_scope.employee_link_query_conditions",
    "Workforce Employee Biometric": "workforce_suite.workforce_suite.report_scope.employee_link_query_conditions",
    "Attendance": "workforce_suite.workforce_suite.report_scope.employee_link_query_conditions",
    "Attendance Request": "workforce_suite.workforce_suite.report_scope.employee_link_query_conditions",
    "Employee Checkin": "workforce_suite.workforce_suite.report_scope.employee_link_query_conditions",
    "Salary Structure Assignment": "workforce_suite.workforce_suite.report_scope.employee_link_query_conditions",
    "Workforce Flexible Work Policy": "workforce_suite.workforce_suite.flexible_work_records.flexible_policy_query_conditions",
    "Workforce Operational Day Override": "workforce_suite.workforce_suite.flexible_work_records.operational_override_query_conditions",
    "Workforce Working Time Rule Set": "workforce_suite.workforce_suite.working_time_compliance.working_time_query_conditions",
    "Workforce Working Time Classification": "workforce_suite.workforce_suite.working_time_compliance.working_time_query_conditions",
    "Workforce Statutory Rule Set": "workforce_suite.workforce_suite.statutory_exit.statutory_ruleset_query_conditions",
    "Workforce Maternity Rule Set": "workforce_suite.workforce_suite.maternity_welfare.maternity_rule_query_conditions",
    "Workforce Maternity Review": "workforce_suite.workforce_suite.maternity_welfare.maternity_sensitive_query_conditions",
    "Workforce Maternity Separation Review": "workforce_suite.workforce_suite.maternity_welfare.maternity_sensitive_query_conditions",
    "Workforce Workplace Welfare Review": "workforce_suite.workforce_suite.maternity_welfare.welfare_query_conditions",
    "Workforce Wage Floor Rule Set": "workforce_suite.workforce_suite.wage_floor.wage_floor_query_conditions",
    "Workforce Wage Floor Classification": "workforce_suite.workforce_suite.wage_floor.wage_floor_query_conditions",
    "Job Opening": "workforce_suite.workforce_suite.joiner_readiness.job_opening_query_conditions",
    "Job Applicant": "workforce_suite.workforce_suite.joiner_readiness.job_applicant_query_conditions",
    "Job Offer": "workforce_suite.workforce_suite.joiner_readiness.job_offer_query_conditions",
    "Interview": "workforce_suite.workforce_suite.joiner_readiness.interview_query_conditions",
    "Interview Feedback": "workforce_suite.workforce_suite.joiner_readiness.interview_feedback_query_conditions",
    "Employee Onboarding": "workforce_suite.workforce_suite.joiner_readiness.employee_onboarding_query_conditions",
}

has_permission = {
    "Workforce Mobile Event": "workforce_suite.workforce_suite.report_scope.employee_link_has_permission",
    "Leave Policy Assignment": "workforce_suite.workforce_suite.report_scope.employee_link_has_permission",
    "Leave Application": "workforce_suite.workforce_suite.report_scope.employee_link_has_permission",
    "Full and Final Statement": "workforce_suite.workforce_suite.report_scope.employee_link_has_permission",
    "Workforce Field Duty": "workforce_suite.workforce_suite.report_scope.employee_link_has_permission",
    "Workforce Location Ping": "workforce_suite.workforce_suite.report_scope.employee_link_has_permission",

    "Payroll Entry": "workforce_suite.workforce_suite.report_scope.payroll_entry_has_permission",
    "Shift Assignment": "workforce_suite.workforce_suite.report_scope.employee_link_has_permission",
    "Shift Schedule Assignment": "workforce_suite.workforce_suite.report_scope.employee_link_has_permission",
    "Shift Request": "workforce_suite.workforce_suite.report_scope.employee_link_has_permission",
    "Leave Allocation": "workforce_suite.workforce_suite.report_scope.employee_link_has_permission",
    "Additional Salary": "workforce_suite.workforce_suite.report_scope.employee_link_has_permission",
    "Overtime Slip": "workforce_suite.workforce_suite.report_scope.employee_link_has_permission",
    "Workforce Employee Biometric": "workforce_suite.workforce_suite.report_scope.employee_link_has_permission",
    "Attendance": "workforce_suite.workforce_suite.report_scope.employee_link_has_permission",
    "Attendance Request": "workforce_suite.workforce_suite.report_scope.employee_link_has_permission",
    "Employee Checkin": "workforce_suite.workforce_suite.report_scope.employee_link_has_permission",
    "Salary Structure Assignment": "workforce_suite.workforce_suite.report_scope.employee_link_has_permission",
    "Workforce Flexible Work Policy": "workforce_suite.workforce_suite.flexible_work_records.flexible_work_has_permission",
    "Workforce Operational Day Override": "workforce_suite.workforce_suite.flexible_work_records.flexible_work_has_permission",
    "Salary Slip": "workforce_suite.workforce_suite.native_payroll.restrict_salary_slip_delete",
    "Job Opening": "workforce_suite.workforce_suite.joiner_readiness.recruitment_has_permission",
    "Job Applicant": "workforce_suite.workforce_suite.joiner_readiness.recruitment_has_permission",
    "Job Offer": "workforce_suite.workforce_suite.joiner_readiness.recruitment_has_permission",
    "Interview": "workforce_suite.workforce_suite.joiner_readiness.recruitment_has_permission",
    "Interview Feedback": "workforce_suite.workforce_suite.joiner_readiness.recruitment_has_permission",
    "Employee Onboarding": "workforce_suite.workforce_suite.joiner_readiness.recruitment_has_permission",
    "Workforce Working Time Rule Set": "workforce_suite.workforce_suite.working_time_compliance.working_time_has_permission",
    "Workforce Working Time Classification": "workforce_suite.workforce_suite.working_time_compliance.working_time_has_permission",
    "Workforce Maternity Rule Set": "workforce_suite.workforce_suite.maternity_welfare.maternity_rule_has_permission",
    "Workforce Maternity Review": "workforce_suite.workforce_suite.maternity_welfare.maternity_sensitive_has_permission",
    "Workforce Maternity Separation Review": "workforce_suite.workforce_suite.maternity_welfare.maternity_sensitive_has_permission",
    "Workforce Workplace Welfare Review": "workforce_suite.workforce_suite.maternity_welfare.welfare_has_permission",
    "Workforce Wage Floor Rule Set": "workforce_suite.workforce_suite.wage_floor.wage_floor_has_permission",
    "Workforce Wage Floor Classification": "workforce_suite.workforce_suite.wage_floor.wage_floor_has_permission",
    "Payroll Correction": "workforce_suite.workforce_suite.payroll_adjustments.adjustment_has_permission",
    "Arrear": "workforce_suite.workforce_suite.payroll_adjustments.adjustment_has_permission",
}

# Require original actors only for scoped HR mutation jobs; unrelated retries pass.
before_job = ["workforce_suite.workforce_suite.bulk_execution_safety.validate_job_actor"]
