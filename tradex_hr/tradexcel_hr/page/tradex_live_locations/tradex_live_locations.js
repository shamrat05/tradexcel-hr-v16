frappe.pages["tradex_live_locations"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({parent: wrapper, title: __("Live Locations"), single_column: true});
  const root = $(wrapper).find(".layout-main-section");
  root.html(
    '<div class="container-fluid tradex-live-locations">' +
    '<div class="card p-3 mb-3"><div class="d-flex justify-content-between align-items-center"><div><h3 class="mb-1">' + __("Live Locations") + '</h3><div class="text-muted" data-status>' + __("Loading...") + '</div></div><button class="btn btn-secondary" data-refresh>' + __("Refresh") + '</button></div></div>' +
    '<div class="card"><div class="table-responsive"><table class="table table-hover mb-0"><thead><tr><th>' + __("Employee") + '</th><th>' + __("Duty") + '</th><th>' + __("Last Seen") + '</th><th>' + __("Accuracy") + '</th><th>' + __("Position") + '</th><th>' + __("Integrity") + '</th></tr></thead><tbody data-rows></tbody></table></div></div>' +
    '</div>'
  );
  const status = root.find("[data-status]");
  const rows = root.find("[data-rows]");
  function esc(value) { return frappe.utils.escape_html(String(value ?? "")); }
  async function refresh() {
    status.text(__("Refreshing..."));
    try {
      const response = await frappe.call({method: "tradex_hr.tradexcel_hr.field_attendance_service.get_live_locations"});
      const locations = response.message || [];
      rows.empty();
      if (!locations.length) rows.append('<tr><td colspan="6" class="text-muted text-center p-4">' + __("No active-duty locations received yet.") + '</td></tr>');
      locations.forEach((row) => {
        const map = "https://www.openstreetmap.org/?mlat=" + encodeURIComponent(row.latitude) + "&mlon=" + encodeURIComponent(row.longitude) + "#map=17/" + encodeURIComponent(row.latitude) + "/" + encodeURIComponent(row.longitude);
        const integrity = row.suspicious_jump ? '<span class="text-danger">' + __("Suspicious jump") + '</span>' : __("Normal");
        rows.append('<tr><td>' + esc(row.employee_name) + '<br><small class="text-muted">' + esc(row.employee) + '</small></td><td>' + esc(row.field_duty) + '</td><td>' + esc(row.ping_time) + '</td><td>' + esc(Math.round(row.accuracy_m || 0)) + ' m</td><td><a target="_blank" rel="noopener" href="' + map + '">' + esc(Number(row.latitude).toFixed(5)) + ', ' + esc(Number(row.longitude).toFixed(5)) + '</a></td><td>' + integrity + '</td></tr>');
      });
      status.text(__("Last refreshed {0} · {1} employee(s)", [frappe.datetime.now_datetime(), locations.length]));
    } catch (error) {
      status.addClass("text-danger").text(error.message || __("Live location access failed."));
    }
  }
  root.find("[data-refresh]").on("click", refresh);
  refresh();
  window.setInterval(refresh, 60000);
};
