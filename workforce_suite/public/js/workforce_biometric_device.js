frappe.ui.form.on("Workforce Biometric Device", {
  refresh(frm) {
    if (frm.is_new() || !frm.has_perm("write")) return;

    // Put the safe diagnostic first. Configuration writes are a secondary
    // device-management operation and stay available under a named group.
    frm.add_custom_button(__("Check Bridge Health"), () => {
      return frappe.call({
        method: "workforce_suite.api.check_device_bridge",
        args: { device_name: frm.doc.name },
        freeze: true,
        freeze_message: __("Checking bridge health")
      }).then(() => frm.reload_doc());
    });

    frm.add_custom_button(__("Push Configuration to Bridge"), () => {
      return frappe.call({
        method: "workforce_suite.api.push_device_configuration",
        args: { device_name: frm.doc.name },
        freeze: true,
        freeze_message: __("Pushing bridge configuration")
      }).then(() => {
        frappe.msgprint(__("Bridge profile saved. The physical terminal still needs the same values under Cloud Server Settings, then a restart."));
        frm.reload_doc();
      });
    }, __("Device actions"));
  }
});
