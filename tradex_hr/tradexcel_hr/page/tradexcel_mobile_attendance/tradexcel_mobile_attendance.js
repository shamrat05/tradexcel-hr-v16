frappe.pages["tradexcel_mobile_attendance"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({parent: wrapper, title: __("Mobile Attendance"), single_column: true});
  const root = $(wrapper).find(".layout-main-section");
  root.html(
    '<div class="tradex-mobile-attendance container-fluid">' +
    '<div class="card p-4 mb-3"><h3>' + __("Mobile Attendance") + '</h3>' +
    '<div class="text-muted" data-context>' + __("Loading employee policy...") + '</div>' +
    '<div class="mt-2" data-last></div></div>' +
    '<div class="card p-4"><label>' + __("Official duty / reason") + '</label>' +
    '<textarea class="form-control mb-3" data-purpose rows="2"></textarea>' +
    '<label>' + __("Selfie evidence") + '</label>' +
    '<input class="form-control mb-3" data-selfie type="file" accept="image/*" capture="user">' +
    '<div class="small text-muted mb-3" data-location>' + __("Location is requested when you press the button.") + '</div>' +
    '<button class="btn btn-primary btn-lg w-100" data-action disabled>' + __("Loading...") + '</button>' +
    '<div class="small mt-3" data-result></div></div></div>'
  );
  const contextEl = root.find("[data-context]");
  const lastEl = root.find("[data-last]");
  const locationEl = root.find("[data-location]");
  const resultEl = root.find("[data-result]");
  const actionEl = root.find("[data-action]");
  let context = null;

  function syncId(prefix) {
    return prefix + "-" + Date.now() + "-" + Math.random().toString(16).slice(2);
  }
  function currentLocation() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) return reject(new Error(__("This browser has no GPS support.")));
      navigator.geolocation.getCurrentPosition(resolve, (error) => reject(new Error(error.message || __("GPS permission was denied."))), {
        enableHighAccuracy: true, timeout: 15000, maximumAge: 30000
      });
    });
  }
  async function uploadSelfie(file) {
    if (!file) return null;
    const form = new FormData();
    form.append("file", file);
    form.append("is_private", "1");
    const response = await fetch("/api/method/upload_file", {
      method: "POST", headers: {"X-Frappe-CSRF-Token": frappe.csrf_token}, body: form
    });
    const payload = await response.json();
    if (!response.ok || payload.exc) throw new Error(__("Selfie upload failed."));
    return payload.message && payload.message.file_url;
  }
  function refreshButton() {
    if (context) actionEl.prop("disabled", false).text(context.next_action === "IN" ? __("Check In") : __("Check Out"));
  }
  async function loadContext() {
    const response = await frappe.call({method: "tradex_hr.tradexcel_hr.field_attendance_service.get_mobile_context"});
    context = response.message;
    contextEl.text(context.employee_name + " · " + context.attendance_mode + " · " + context.company);
    lastEl.text(context.last_checkin ? __("Last {0}: {1}", [context.last_checkin.log_type, context.last_checkin.time]) : __("No mobile check-in yet"));
    refreshButton();
  }
  actionEl.on("click", async () => {
    actionEl.prop("disabled", true);
    resultEl.removeClass("text-danger text-success").text(__("Requesting location..."));
    try {
      const position = await currentLocation();
      locationEl.text(__("GPS: {0}, {1} · accuracy {2} m", [position.coords.latitude.toFixed(5), position.coords.longitude.toFixed(5), Math.round(position.coords.accuracy || 0)]));
      const file = root.find("[data-selfie]")[0].files[0];
      if (context.require_selfie && !file) throw new Error(__("A selfie is required for this attendance policy."));
      resultEl.text(file ? __("Uploading selfie and recording attendance...") : __("Recording attendance..."));
      const selfieUrl = file ? await uploadSelfie(file) : null;
      const response = await frappe.call({
        method: "tradex_hr.tradexcel_hr.field_attendance_service.mobile_checkin",
        args: {employee: context.employee, log_type: context.next_action, latitude: position.coords.latitude, longitude: position.coords.longitude, accuracy_m: position.coords.accuracy, time: new Date().toISOString(), sync_id: syncId("mobile"), selfie: selfieUrl}
      });
      const checkin = response.message;
      if (selfieUrl) await frappe.call({method: "tradex_hr.tradexcel_hr.field_attendance_service.attach_selfie", args: {checkin: checkin.name, file_url: selfieUrl}});
      resultEl.addClass("text-success").text(__("Attendance recorded successfully."));
      await loadContext();
    } catch (error) {
      resultEl.addClass("text-danger").text(error.message || __("Attendance could not be recorded."));
      refreshButton();
    }
  });
  loadContext().catch((error) => contextEl.addClass("text-danger").text(error.message || __("Employee policy is not configured.")));
};
