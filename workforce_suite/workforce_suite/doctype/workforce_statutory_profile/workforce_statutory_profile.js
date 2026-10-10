frappe.ui.form.on("Workforce Statutory Profile", {
    refresh(frm) {
        if (frm.is_new()) return;
        frappe.call({
            method: "workforce_suite.workforce_suite.statutory_setup.profile_missing_requirements",
            args: {profile_name: frm.doc.name},
        }).then((response) => {
            const findings = response.message || [];
            if (!findings.length) {
                frm.set_intro(__("All configured profile requirements are present; independent submission review is still required."), "green");
                return;
            }
            const message = findings.map((item) => __("• {0}", [item.message])).join("<br>");
            frm.set_intro(__("<strong>Review before submission</strong><br>{0}", [message]), "orange");
        });
    },
});
