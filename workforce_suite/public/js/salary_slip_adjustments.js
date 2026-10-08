frappe.ui.form.on("Salary Slip", {
  refresh(frm) {
    if (frm.doc.docstatus !== 1) return;

    frm.add_custom_button(__("Review Payroll Adjustment"), () => {
      frappe.prompt([
        {
          fieldname: "issue_type",
          label: __("What needs correction?"),
          fieldtype: "Select",
          options: [
            "LWP Reversal",
            "Retroactive Salary Increase",
            "Daily Wage Attendance Correction",
            "Overpayment",
          ].join("\n"),
          reqd: 1,
        },
        {
          fieldname: "payroll_date",
          label: __("Target Future Payroll Date"),
          fieldtype: "Date",
          reqd: 1,
        },
      ], (values) => {
        const types = {
          "LWP Reversal": "lwp",
          "Retroactive Salary Increase": "salary_structure",
          "Daily Wage Attendance Correction": "daily_wage",
          "Overpayment": "overpayment",
        };

        frappe.call({
          method: "workforce_suite.workforce_suite.payroll_adjustments.inspect_payroll_adjustment_readiness",
          args: {
            salary_slip: frm.doc.name,
            issue_type: types[values.issue_type],
            payroll_date: values.payroll_date,
          },
        }).then(({ message }) => {
          if (message.status === "LWP_REVERSAL_AVAILABLE") {
            frappe.route_options = {
              employee: frm.doc.employee,
              company: frm.doc.company,
              payroll_period: frm.doc.current_payroll_period,
              payroll_date: values.payroll_date,
              salary_slip_reference: frm.doc.name,
            };
            frappe.new_doc("Payroll Correction");
            return;
          }

          if (message.status === "SALARY_ARREAR_AVAILABLE") {
            frappe.route_options = {
              employee: frm.doc.employee,
              company: frm.doc.company,
              payroll_period: frm.doc.current_payroll_period,
              arrear_start_date: frm.doc.start_date,
              payroll_date: values.payroll_date,
            };
            frappe.new_doc("Arrear");
            return;
          }

          frappe.msgprint({
            title: __("Payroll Adjustment Review"),
            message: __(message.next_action || message.status),
            indicator: message.status === "RETRO_OVERPAYMENT_DECISION_REQUIRED" ? "orange" : "blue",
          });
        });
      }, __("Review Post-Payroll Adjustment"), __("Continue"));
    }, __("Payroll"));
  },
});
