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

add_to_apps_screen = [{
    "name": "tradex_hr",
    "logo": "/assets/tradex_hr/images/tradex-hr.svg",
    "title": "Tradexcel HR",
    "route": "/app/tradexcel-hr",
}]

extend_doctype_class = {
    "Employee Transfer": [
        "tradex_hr.tradexcel_hr.employee_lifecycle.EmployeeTransferLifecycleMixin",
    ],
    "Employee Promotion": [
        "tradex_hr.tradexcel_hr.employee_lifecycle.EmployeePromotionLifecycleMixin",
    ],
    "Payroll Entry": [
        "tradex_hr.tradexcel_hr.payroll_finalization.PayrollEntryFinalizationMixin",
    ],
    "Payroll Correction": [
        "tradex_hr.tradexcel_hr.payroll_adjustments.PayrollCorrectionMixin",
    ],
    "Arrear": [
        "tradex_hr.tradexcel_hr.payroll_adjustments.TradexcelArrearMixin",
    ],
    "Full and Final Statement": [
        "tradex_hr.tradexcel_hr.employee_separation.FullAndFinalTradexcelMixin",
    ],
    "Shift Assignment Tool": [
        "tradex_hr.tradexcel_hr.shift_assignment_tool.TradexcelShiftAssignmentToolMixin",
    ],
    "Bulk Salary Structure Assignment": [
        "tradex_hr.tradexcel_hr.bulk_salary_structure_assignment.TradexcelBulkSalaryStructureAssignmentMixin",
    ],
}

doctype_js = {
    "Tradexcel Biometric Device": "public/js/tradexcel_biometric_device.js",
    "Payroll Entry": "public/js/payroll_entry.js",
    "Salary Slip": "public/js/salary_slip_adjustments.js",
    "Employee": "public/js/employee_calendar.js",
    "Employee Separation": "public/js/employee_separation.js",
    "Attendance": "public/js/employee_calendar.js",
    "Shift Assignment Tool": "public/js/shift_assignment_tool.js",
    "Bulk Salary Structure Assignment": "public/js/bulk_salary_structure_assignment.js",
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
    "Payroll Correction": {
        "before_insert": "tradex_hr.tradexcel_hr.payroll_adjustments.initialize_adjustment_state",
        "validate": "tradex_hr.tradexcel_hr.payroll_adjustments.validate_payroll_correction",
        "before_save": "tradex_hr.tradexcel_hr.payroll_adjustments.validate_adjustment_before_save",
        "before_submit": "tradex_hr.tradexcel_hr.payroll_adjustments.validate_adjustment_before_submit",
        "before_cancel": "tradex_hr.tradexcel_hr.payroll_adjustments.validate_adjustment_before_cancel",
    },
    "Arrear": {
        "before_insert": "tradex_hr.tradexcel_hr.payroll_adjustments.initialize_adjustment_state",
        "validate": "tradex_hr.tradexcel_hr.payroll_adjustments.validate_arrear",
        "before_save": "tradex_hr.tradexcel_hr.payroll_adjustments.validate_adjustment_before_save",
        "before_submit": "tradex_hr.tradexcel_hr.payroll_adjustments.validate_adjustment_before_submit",
        "before_cancel": "tradex_hr.tradexcel_hr.payroll_adjustments.validate_adjustment_before_cancel",
    },
    "Additional Salary": {
        "before_submit": "tradex_hr.tradexcel_hr.working_time_compliance.validate_overtime_generated_additional_salary",
        "before_cancel": "tradex_hr.tradexcel_hr.payroll_adjustments.validate_additional_salary_before_cancel",
    },
    "Payroll Entry": {
        "before_submit": "tradex_hr.tradexcel_hr.native_payroll.validate_payroll_entry_before_submit",
        # A submitted Payroll Entry workflow transition uses save()'s
        # before_update_after_submit event; validate() is not run by Frappe in
        # that lifecycle, so enforce the gate at the native transition hook.
        "before_update_after_submit": "tradex_hr.tradexcel_hr.financial_readiness.validate_payroll_financial_readiness_before_approval",
    },
    "Salary Slip": {
        "before_submit": [
            "tradex_hr.tradexcel_hr.native_payroll.validate_salary_slip_before_submit",
            "tradex_hr.tradexcel_hr.maternity_welfare.validate_maternity_salary_slip",
        ],
        "before_validate": "tradex_hr.tradexcel_hr.component_exceptions.apply_to_salary_slip",
    },
    "Attendance": {
        "before_save": "tradex_hr.tradexcel_hr.attendance_exceptions.apply_to_attendance",
        "validate": "tradex_hr.tradexcel_hr.attendance_exceptions.sync_scope_fields",
        "before_submit": [
            "tradex_hr.tradexcel_hr.employee_separation.validate_no_payable_work_after_relieving_date",
            "tradex_hr.tradexcel_hr.maternity_welfare.validate_maternity_attendance",
        ],
    },
    "Attendance Request": {
        "validate": "tradex_hr.tradexcel_hr.employee_separation.validate_no_payable_work_after_relieving_date",
        "before_submit": "tradex_hr.tradexcel_hr.attendance_corrections.validate_attendance_request_before_submit",
        "before_cancel": "tradex_hr.tradexcel_hr.attendance_corrections.validate_attendance_request_before_cancel",
    },
    "Overtime Slip": {
        "validate": "tradex_hr.tradexcel_hr.employee_separation.validate_no_payable_work_after_relieving_date",
        "before_submit": [
            "tradex_hr.tradexcel_hr.working_time_compliance.validate_overtime_slip_before_submit",
            "tradex_hr.tradexcel_hr.maternity_welfare.validate_maternity_overtime",
        ],
    },
    "Tradexcel Field Duty": {
        "validate": [
            "tradex_hr.tradexcel_hr.employee_separation.validate_no_payable_work_after_relieving_date",
            "tradex_hr.tradexcel_hr.maternity_welfare.validate_maternity_field_duty",
        ],
    },
    "Employee Separation": {
        "validate": "tradex_hr.tradexcel_hr.employee_separation.validate_employee_separation",
        "before_submit": "tradex_hr.tradexcel_hr.maternity_welfare.validate_maternity_employee_separation",
    },
    "Employee Transfer": {
        "validate": "tradex_hr.tradexcel_hr.employee_lifecycle.validate_employee_transfer",
    },
    "Employee Promotion": {
        "validate": "tradex_hr.tradexcel_hr.employee_lifecycle.validate_employee_promotion",
    },
    "Full and Final Statement": {
        "before_submit": [
            "tradex_hr.tradexcel_hr.employee_separation.validate_full_and_final_before_submit",
            "tradex_hr.tradexcel_hr.maternity_welfare.validate_maternity_full_and_final",
        ],
    },
    "Tradexcel Maternity Rule Set": {
        "validate": "tradex_hr.tradexcel_hr.maternity_welfare.validate_maternity_rule_set",
        "before_submit": "tradex_hr.tradexcel_hr.maternity_welfare.validate_maternity_rule_submit",
        "before_update_after_submit": "tradex_hr.tradexcel_hr.maternity_welfare.before_update_after_submit_maternity_rule",
        "before_cancel": "tradex_hr.tradexcel_hr.maternity_welfare.prevent_maternity_rule_cancel",
    },
    "Tradexcel Maternity Review": {
        "validate": "tradex_hr.tradexcel_hr.maternity_welfare.validate_maternity_review",
        "before_submit": "tradex_hr.tradexcel_hr.maternity_welfare.before_submit_maternity_review",
        "before_update_after_submit": "tradex_hr.tradexcel_hr.maternity_welfare.before_update_after_submit_maternity_review",
        "before_cancel": "tradex_hr.tradexcel_hr.maternity_welfare.before_cancel_maternity_review",
    },
    "Tradexcel Maternity Separation Review": {
        "validate": "tradex_hr.tradexcel_hr.maternity_welfare.validate_maternity_separation_review",
        "before_submit": "tradex_hr.tradexcel_hr.maternity_welfare.before_submit_maternity_separation_review",
        "before_update_after_submit": "tradex_hr.tradexcel_hr.maternity_welfare.before_update_after_submit_maternity_separation_review",
        "before_cancel": "tradex_hr.tradexcel_hr.maternity_welfare.before_cancel_maternity_separation_review",
    },
    "Tradexcel Workplace Welfare Review": {
        "validate": "tradex_hr.tradexcel_hr.maternity_welfare.validate_workplace_welfare_review",
        "before_submit": "tradex_hr.tradexcel_hr.maternity_welfare.before_submit_workplace_welfare_review",
        "before_update_after_submit": "tradex_hr.tradexcel_hr.maternity_welfare.before_update_after_submit_workplace_welfare_review",
        "before_cancel": "tradex_hr.tradexcel_hr.maternity_welfare.before_cancel_workplace_welfare_review",
    },
    "Tradexcel Statutory Rule Set": {
        "validate": "tradex_hr.tradexcel_hr.statutory_exit.validate_statutory_ruleset",
        "before_submit": "tradex_hr.tradexcel_hr.statutory_exit.before_submit_statutory_ruleset",
        "before_update_after_submit": "tradex_hr.tradexcel_hr.statutory_exit.before_update_after_submit_statutory_ruleset",
        "before_cancel": "tradex_hr.tradexcel_hr.statutory_exit.before_cancel_statutory_ruleset",
    },
    "Employee Onboarding": {
        "validate": "tradex_hr.tradexcel_hr.joiner_readiness.validate_employee_onboarding",
    },
    "Job Opening": {
        "validate": "tradex_hr.tradexcel_hr.joiner_readiness.validate_recruitment_company_scope",
    },
    "Job Applicant": {
        "validate": "tradex_hr.tradexcel_hr.joiner_readiness.validate_recruitment_company_scope",
    },
    "Job Offer": {
        "validate": "tradex_hr.tradexcel_hr.joiner_readiness.validate_recruitment_company_scope",
    },
    "Interview": {
        "validate": "tradex_hr.tradexcel_hr.joiner_readiness.validate_recruitment_company_scope",
    },
    "Interview Feedback": {
        "validate": "tradex_hr.tradexcel_hr.joiner_readiness.validate_recruitment_company_scope",
    },
    "Employee": {
        "before_insert": "tradex_hr.tradexcel_hr.joiner_readiness.validate_unique_employee_job_applicant",
        "validate": [
            "tradex_hr.tradexcel_hr.employee_lifecycle.validate_employee_lifecycle_fields",
            "tradex_hr.tradexcel_hr.employee_lifecycle.validate_employee_employment_spell",
        ],
    },
    "Salary Structure Assignment": {
        "validate": "tradex_hr.tradexcel_hr.employee_lifecycle.validate_salary_structure_assignment",
        "before_submit": "tradex_hr.tradexcel_hr.employee_lifecycle.validate_salary_structure_assignment_before_submit",
        "before_cancel": "tradex_hr.tradexcel_hr.employee_lifecycle.validate_salary_structure_assignment_before_cancel",
    },
    "Employee Checkin": {
        "before_validate": "tradex_hr.tradexcel_hr.field_attendance_service.enrich_mobile_checkin",
    },
}

after_install = "tradex_hr.install.after_install"
after_migrate = "tradex_hr.install.after_migrate"


permission_query_conditions = {
    "Tradexcel Flexible Work Policy": "tradex_hr.tradexcel_hr.flexible_work_records.flexible_policy_query_conditions",
    "Tradexcel Operational Day Override": "tradex_hr.tradexcel_hr.flexible_work_records.operational_override_query_conditions",
    "Tradexcel Working Time Rule Set": "tradex_hr.tradexcel_hr.working_time_compliance.working_time_query_conditions",
    "Tradexcel Working Time Classification": "tradex_hr.tradexcel_hr.working_time_compliance.working_time_query_conditions",
    "Tradexcel Statutory Rule Set": "tradex_hr.tradexcel_hr.statutory_exit.statutory_ruleset_query_conditions",
    "Tradexcel Maternity Rule Set": "tradex_hr.tradexcel_hr.maternity_welfare.maternity_rule_query_conditions",
    "Tradexcel Maternity Review": "tradex_hr.tradexcel_hr.maternity_welfare.maternity_sensitive_query_conditions",
    "Tradexcel Maternity Separation Review": "tradex_hr.tradexcel_hr.maternity_welfare.maternity_sensitive_query_conditions",
    "Tradexcel Workplace Welfare Review": "tradex_hr.tradexcel_hr.maternity_welfare.welfare_query_conditions",
    "Tradexcel Wage Floor Rule Set": "tradex_hr.tradexcel_hr.wage_floor.wage_floor_query_conditions",
    "Tradexcel Wage Floor Classification": "tradex_hr.tradexcel_hr.wage_floor.wage_floor_query_conditions",
    "Job Opening": "tradex_hr.tradexcel_hr.joiner_readiness.job_opening_query_conditions",
    "Job Applicant": "tradex_hr.tradexcel_hr.joiner_readiness.job_applicant_query_conditions",
    "Job Offer": "tradex_hr.tradexcel_hr.joiner_readiness.job_offer_query_conditions",
    "Interview": "tradex_hr.tradexcel_hr.joiner_readiness.interview_query_conditions",
    "Interview Feedback": "tradex_hr.tradexcel_hr.joiner_readiness.interview_feedback_query_conditions",
    "Employee Onboarding": "tradex_hr.tradexcel_hr.joiner_readiness.employee_onboarding_query_conditions",
}

has_permission = {
    "Tradexcel Flexible Work Policy": "tradex_hr.tradexcel_hr.flexible_work_records.flexible_work_has_permission",
    "Tradexcel Operational Day Override": "tradex_hr.tradexcel_hr.flexible_work_records.flexible_work_has_permission",
    "Salary Slip": "tradex_hr.tradexcel_hr.native_payroll.restrict_salary_slip_delete",
    "Job Opening": "tradex_hr.tradexcel_hr.joiner_readiness.recruitment_has_permission",
    "Job Applicant": "tradex_hr.tradexcel_hr.joiner_readiness.recruitment_has_permission",
    "Job Offer": "tradex_hr.tradexcel_hr.joiner_readiness.recruitment_has_permission",
    "Interview": "tradex_hr.tradexcel_hr.joiner_readiness.recruitment_has_permission",
    "Interview Feedback": "tradex_hr.tradexcel_hr.joiner_readiness.recruitment_has_permission",
    "Employee Onboarding": "tradex_hr.tradexcel_hr.joiner_readiness.recruitment_has_permission",
    "Tradexcel Working Time Rule Set": "tradex_hr.tradexcel_hr.working_time_compliance.working_time_has_permission",
    "Tradexcel Working Time Classification": "tradex_hr.tradexcel_hr.working_time_compliance.working_time_has_permission",
    "Tradexcel Maternity Rule Set": "tradex_hr.tradexcel_hr.maternity_welfare.maternity_rule_has_permission",
    "Tradexcel Maternity Review": "tradex_hr.tradexcel_hr.maternity_welfare.maternity_sensitive_has_permission",
    "Tradexcel Maternity Separation Review": "tradex_hr.tradexcel_hr.maternity_welfare.maternity_sensitive_has_permission",
    "Tradexcel Workplace Welfare Review": "tradex_hr.tradexcel_hr.maternity_welfare.welfare_has_permission",
    "Tradexcel Wage Floor Rule Set": "tradex_hr.tradexcel_hr.wage_floor.wage_floor_has_permission",
    "Tradexcel Wage Floor Classification": "tradex_hr.tradexcel_hr.wage_floor.wage_floor_has_permission",
    "Payroll Correction": "tradex_hr.tradexcel_hr.payroll_adjustments.adjustment_has_permission",
    "Arrear": "tradex_hr.tradexcel_hr.payroll_adjustments.adjustment_has_permission",
}
