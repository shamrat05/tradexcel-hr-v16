frappe.ui.form.on("Tradexcel Biometric Device", {
  refresh(frm) {
    if (frm.is_new()) return;
    frm.add_custom_button(__("Push Configuration to Bridge"), () => {
      frappe.call({
        method: "tradex_hr.api.push_device_configuration",
        args: {device_name: frm.doc.name},
        freeze: true,
        freeze_message: __("Pushing bridge configuration")
      }).then(r => {
        frappe.msgprint(__("Bridge profile saved. The physical terminal still needs the same values under Cloud Server Settings, then a restart."));
        frm.reload_doc();
      });
    });
    frm.add_custom_button(__("Check Bridge Health"), () => {
      frappe.call({
        method: "tradex_hr.api.check_device_bridge",
        args: {device_name: frm.doc.name},
        freeze: true,
        freeze_message: __("Checking bridge health")
      }).then(() => frm.reload_doc());
    });
  }
});
