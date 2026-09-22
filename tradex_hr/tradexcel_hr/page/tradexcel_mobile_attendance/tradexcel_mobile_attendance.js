frappe.pages["tradexcel-mobile-attendance"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({parent: wrapper, title: __("Mobile Attendance"), single_column: true});
  const root = $(wrapper).find(".layout-main-section");
  root.html(
    '<div class="tradex-mobile-attendance container-fluid">' +
    '<div class="card p-4 mb-3"><h3>' + __("Mobile Attendance") + '</h3>' +
    '<div class="text-muted" data-context>' + __("Loading employee policy...") + '</div>' +
    '<div class="mt-2" data-last></div></div>' +
    '<div class="card p-4" data-attendance-form>' +
    '<h4 class="mb-3" data-form-title>' + __("Check In") + '</h4>' +
    '<label>' + __("Official duty / reason") + '</label>' +
    '<textarea class="form-control mb-3" data-purpose rows="2"></textarea>' +
    '<label>' + __("Live selfie (camera)") + '</label>' +
    '<input class="form-control mb-3" data-selfie type="file" accept="image/*" capture="user">' +
    '<div class="d-none mt-3" data-selfie-preview-wrap>' +
    '<div class="small text-muted mb-2">' + __("Captured selfie preview") + '</div>' +
    '<img class="img-fluid rounded border" data-selfie-preview alt="' + __("Captured selfie") + '" style="max-height:320px;object-fit:contain;width:100%;">' +
    '<div class="small text-muted mt-2" data-selfie-meta></div></div>' +
    '<div class="small text-muted mb-3" data-location>' + __("Location is requested when you press the button.") + '</div>' +
    '<button class="btn btn-primary btn-lg w-100" data-action disabled>' + __("Loading...") + '</button>' +
    '<div class="small mt-3" data-result></div>' +
    '<div class="small mt-2" data-queue-status></div></div>' +
    '<div class="d-none card border-success text-center p-5" data-success-state role="status" aria-live="polite">' +
    '<div class="display-4 text-success mb-3">✓</div>' +
    '<h2 class="text-success" data-success-title>' + __("Attendance recorded") + '</h2>' +
    '<p class="lead mb-4" data-success-detail></p>' +
    '<button class="btn btn-success btn-lg w-100" data-success-action></button></div></div>'
  );
  const attendanceForm = root.find("[data-attendance-form]");
  const formTitle = root.find("[data-form-title]");
  const successState = root.find("[data-success-state]");
  const successTitle = root.find("[data-success-title]");
  const successDetail = root.find("[data-success-detail]");
  const successAction = root.find("[data-success-action]");
  const contextEl = root.find("[data-context]");
  const lastEl = root.find("[data-last]");
  const locationEl = root.find("[data-location]");
  const resultEl = root.find("[data-result]");
  const queueStatusEl = root.find("[data-queue-status]");
  const actionEl = root.find("[data-action]");
  const selfieInput = root.find("[data-selfie]");
  const selfiePreviewWrap = root.find("[data-selfie-preview-wrap]");
  const selfiePreview = root.find("[data-selfie-preview]");
  const selfieMeta = root.find("[data-selfie-meta]");
  let context = null;
  let trackingTimer = null;
  let watchId = null;
  let lastPosition = null;
  let selfiePreviewUrl = null;
  let offlineFlushInProgress = false;

  const OFFLINE_DB_NAME = "tradex_mobile_attendance";
  const OFFLINE_STORE_NAME = "events";

  function openOfflineDb() {
    return new Promise((resolve, reject) => {
      if (!window.indexedDB) return reject(new Error(__("This browser cannot store offline attendance.")));
      const request = window.indexedDB.open(OFFLINE_DB_NAME, 1);
      request.onupgradeneeded = () => {
        if (!request.result.objectStoreNames.contains(OFFLINE_STORE_NAME)) {
          request.result.createObjectStore(OFFLINE_STORE_NAME, {keyPath: "sync_id"});
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error(__("Offline storage is unavailable.")));
    });
  }

  async function withOfflineStore(mode, callback) {
    const db = await openOfflineDb();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(OFFLINE_STORE_NAME, mode);
      const store = transaction.objectStore(OFFLINE_STORE_NAME);
      let result;
      try {
        result = callback(store);
      } catch (error) {
        db.close();
        reject(error);
        return;
      }
      transaction.oncomplete = () => { db.close(); resolve(result); };
      transaction.onerror = () => { db.close(); reject(transaction.error); };
    });
  }

  async function queueOfflineCheckin(payload) {
    await withOfflineStore("readwrite", (store) => store.put({
      ...payload,
      queued_at: new Date().toISOString(),
      retryable: true,
    }));
  }

  async function queuedCheckins() {
    const db = await openOfflineDb();
    return new Promise((resolve, reject) => {
      const request = db.transaction(OFFLINE_STORE_NAME, "readonly").objectStore(OFFLINE_STORE_NAME).getAll();
      request.onsuccess = () => { db.close(); resolve((request.result || []).sort((a, b) => a.queued_at.localeCompare(b.queued_at))); };
      request.onerror = () => { db.close(); reject(request.error); };
    });
  }

  async function deleteQueuedCheckin(syncId) {
    await withOfflineStore("readwrite", (store) => store.delete(syncId));
  }

  function isNetworkError(error) {
    return !navigator.onLine || !error || error.status === 0 || error.readyState === 0 ||
      error.status >= 500 || error.name === "TypeError";
  }

  async function updateQueueStatus() {
    try {
      const items = await queuedCheckins();
      queueStatusEl.removeClass("text-danger text-warning text-success");
      const pending = items.filter((item) => item.retryable !== false);
      const failed = items.filter((item) => item.retryable === false);
      if (!items.length) {
        queueStatusEl.text("");
      } else {
        queueStatusEl.addClass(failed.length ? "text-danger" : "text-warning").text(
          failed.length
            ? __("{0} event(s) need HR attention; {1} event(s) will sync automatically when online.", [failed.length, pending.length])
            : __("{0} attendance event(s) are saved on this device and will sync automatically when online.", [pending.length])
        );
      }
      return items;
    } catch (error) {
      queueStatusEl.addClass("text-danger").text(error.message || __("Offline storage is unavailable."));
      return [];
    }
  }

  function showSelfiePreview(file) {
    if (selfiePreviewUrl) URL.revokeObjectURL(selfiePreviewUrl);
    selfiePreviewUrl = null;
    if (!file) {
      selfiePreviewWrap.addClass("d-none");
      selfiePreview.attr("src", "");
      selfieMeta.text("");
      return;
    }
    selfiePreviewUrl = URL.createObjectURL(file);
    selfiePreview.attr("src", selfiePreviewUrl);
    selfieMeta.text(__("{0} · {1} KB", [file.type || "image", Math.ceil(file.size / 1024)]));
    selfiePreviewWrap.removeClass("d-none");
  }

  function showCheckoutForm() {
    successState.addClass("d-none");
    attendanceForm.removeClass("d-none");
    selfieInput.val("");
    showSelfiePreview(null);
    resultEl.removeClass("text-danger text-success").text("");
    locationEl.text(__("Location is requested when you press the button."));
    if (context) {
      context.next_action = "OUT";
      refreshButton();
    }
  }

  function showSuccessState(logType, checkin, queued) {
    attendanceForm.addClass("d-none");
    successState.removeClass("d-none");
    const canCheckout = logType === "IN";
    const actionLabel = canCheckout ? (queued ? __("Back to work") : __("Check Out")) : __("Done");
    successTitle.text(
      queued
        ? __("Saved on this device")
        : (logType === "IN" ? __("Successfully checked in") : __("Successfully checked out"))
    );
    successDetail.text(
      queued
        ? __("Your attendance is safely queued and will sync automatically when the connection returns.")
        : (logType === "IN"
          ? __("You have successfully checked in at {0}. You can now go back to work.", [checkin.time || __("the current time")])
          : __("You have successfully checked out at {0}.", [checkin.time || __("the current time")]))
    );
    successAction.removeClass("d-none").text(actionLabel).off("click");
    if (canCheckout) {
      successAction.on("click", showCheckoutForm);
    } else {
      successAction.addClass("d-none");
    }
  }

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
    let response;
    try {
      response = await fetch("/api/method/upload_file", {
        method: "POST", headers: {"X-Frappe-CSRF-Token": frappe.csrf_token}, body: form
      });
    } catch (error) {
      error.status = 0;
      throw error;
    }
    const payload = await response.json();
    if (!response.ok || payload.exc) {
      const error = new Error(__("Selfie upload failed."));
      error.status = response.status;
      throw error;
    }
    return payload.message && payload.message.file_url;
  }

  async function replayQueuedCheckin(item) {
    if (!navigator.onLine) return false;
    let selfieUrl = item.selfie_url || null;
    if (item.selfie_blob && !selfieUrl) {
      const file = new File(
        [item.selfie_blob],
        item.selfie_name || "mobile-selfie.jpg",
        {type: item.selfie_type || "image/jpeg"}
      );
      selfieUrl = await uploadSelfie(file);
    }
    const response = await frappe.call({
      method: "tradex_hr.tradexcel_hr.field_attendance_service.mobile_checkin",
      args: {
        employee: item.employee,
        log_type: item.log_type,
        latitude: item.latitude,
        longitude: item.longitude,
        accuracy_m: item.accuracy_m,
        time: item.time,
        field_duty: item.field_duty,
        sync_id: item.sync_id,
        selfie: selfieUrl,
      },
    });
    const checkin = response.message;
    if (selfieUrl && checkin && checkin.name) {
      await frappe.call({
        method: "tradex_hr.tradexcel_hr.field_attendance_service.attach_selfie",
        args: {checkin: checkin.name, file_url: selfieUrl},
      });
    }
    await deleteQueuedCheckin(item.sync_id);
    return true;
  }

  async function flushOfflineQueue() {
    if (offlineFlushInProgress || !navigator.onLine) return;
    offlineFlushInProgress = true;
    try {
      const items = await queuedCheckins();
      for (const item of items.filter((row) => row.retryable !== false)) {
        try {
          await replayQueuedCheckin(item);
        } catch (error) {
          if (isNetworkError(error)) break;
          await withOfflineStore("readwrite", (store) => store.put({...item, retryable: false, last_error: error.message || __("Server rejected event") }));
        }
      }
    } finally {
      offlineFlushInProgress = false;
      await updateQueueStatus();
    }
  }
  function refreshButton() {
    if (context) {
      const label = context.next_action === "IN" ? __("Check In") : __("Check Out");
      formTitle.text(label);
      actionEl.prop("disabled", false).text(label);
    }
  }
  function stopTracking() {
    if (trackingTimer) window.clearInterval(trackingTimer);
    if (watchId !== null && navigator.geolocation) navigator.geolocation.clearWatch(watchId);
    trackingTimer = null;
    watchId = null;
    lastPosition = null;
  }
  function startTracking() {
    stopTracking();
    if (!context || !context.tracking_active || !context.field_duty) return;
    if (!navigator.geolocation) return;
    watchId = navigator.geolocation.watchPosition((position) => {
      lastPosition = position;
    }, () => {}, {enableHighAccuracy: true, maximumAge: 30000, timeout: 15000});
    trackingTimer = window.setInterval(async () => {
      if (!lastPosition) return;
      const position = lastPosition;
      try {
        await frappe.call({
          method: "tradex_hr.tradexcel_hr.field_attendance_service.location_ping",
          args: {
            employee: context.employee,
            field_duty: context.field_duty.name,
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy_m: position.coords.accuracy,
            ping_time: new Date().toISOString(),
            sync_id: syncId("ping")
          }
        });
        locationEl.text(__("Live location sent · accuracy {0} m", [Math.round(position.coords.accuracy || 0)]));
      } catch (error) {
        // The server enforces the interval/duty window. Keep the watch alive
        // so a transient network or interval response does not stop tracking.
      }
    }, Math.max(1, context.tracking_interval_minutes) * 60000);
  }
  selfieInput.on("change", () => showSelfiePreview(selfieInput[0].files[0]));
  async function loadContext() {
    const response = await frappe.call({method: "tradex_hr.tradexcel_hr.field_attendance_service.get_mobile_context"});
    context = response.message;
    contextEl.text(context.employee_name + " · " + context.attendance_mode + " · " + context.company);
    lastEl.text(context.last_checkin ? __("Last {0}: {1}", [context.last_checkin.log_type, context.last_checkin.time]) : __("No mobile check-in yet"));
    const queued = await queuedCheckins().catch(() => []);
    const pendingForEmployee = queued
      .filter((item) => item.employee === context.employee && item.retryable !== false)
      .sort((a, b) => a.queued_at.localeCompare(b.queued_at));
    const latestPending = pendingForEmployee[pendingForEmployee.length - 1];
    if (latestPending) {
      // The server may not know about an offline event yet. Reflect the local
      // state so a reload cannot create a duplicate IN or OUT event.
      context.next_action = latestPending.log_type === "IN" ? "OUT" : "IN";
      showSuccessState(latestPending.log_type, {time: latestPending.time}, true);
    } else {
      successState.addClass("d-none");
      attendanceForm.removeClass("d-none");
    }
    if (context.next_action === "OUT") {
      selfieInput.val("");
      showSelfiePreview(null);
    }
    refreshButton();
    startTracking();
  }
  actionEl.on("click", async () => {
    actionEl.prop("disabled", true);
    resultEl.removeClass("text-danger text-success").text(__("Requesting location..."));
    let queuedPayload = null;
    try {
      const position = await currentLocation();
      locationEl.text(__("GPS: {0}, {1} · accuracy {2} m", [position.coords.latitude.toFixed(5), position.coords.longitude.toFixed(5), Math.round(position.coords.accuracy || 0)]));
      const file = selfieInput[0].files[0];
      if (context.require_selfie && !file) throw new Error(__("A selfie is required for this attendance policy."));
      const completedAction = context.next_action;
      queuedPayload = {
        employee: context.employee,
        log_type: completedAction,
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy_m: position.coords.accuracy,
        time: new Date().toISOString(),
        field_duty: context.field_duty && context.field_duty.name,
        sync_id: syncId("mobile"),
        selfie_blob: file || null,
        selfie_name: file && file.name,
        selfie_type: file && file.type,
      };
      if (!navigator.onLine) {
        await queueOfflineCheckin(queuedPayload);
        await updateQueueStatus();
        showSuccessState(completedAction, {time: queuedPayload.time}, true);
        return;
      }
      resultEl.text(file ? __("Uploading selfie and recording attendance...") : __("Recording attendance..."));
      const selfieUrl = file ? await uploadSelfie(file) : null;
      const requestArgs = {
        employee: queuedPayload.employee,
        log_type: queuedPayload.log_type,
        latitude: queuedPayload.latitude,
        longitude: queuedPayload.longitude,
        accuracy_m: queuedPayload.accuracy_m,
        time: queuedPayload.time,
        field_duty: queuedPayload.field_duty,
        sync_id: queuedPayload.sync_id,
        selfie: selfieUrl,
      };
      const response = await frappe.call({
        method: "tradex_hr.tradexcel_hr.field_attendance_service.mobile_checkin",
        args: requestArgs
      });
      const checkin = response.message;
      if (selfieUrl) await frappe.call({method: "tradex_hr.tradexcel_hr.field_attendance_service.attach_selfie", args: {checkin: checkin.name, file_url: selfieUrl}});
      try {
        await loadContext();
      } catch (contextError) {
        context.next_action = completedAction === "IN" ? "OUT" : "IN";
      }
      showSuccessState(completedAction, checkin);
    } catch (error) {
      if (queuedPayload && isNetworkError(error)) {
        try {
          await queueOfflineCheckin(queuedPayload);
          await updateQueueStatus();
          showSuccessState(queuedPayload.log_type, {time: queuedPayload.time}, true);
          return;
        } catch (queueError) {
          error = queueError;
        }
      }
      resultEl.addClass("text-danger").text(error.message || __("Attendance could not be recorded."));
      refreshButton();
    }
  });
  window.addEventListener("online", flushOfflineQueue);
  loadContext()
    .then(() => Promise.all([updateQueueStatus(), flushOfflineQueue()]))
    .catch((error) => contextEl.addClass("text-danger").text(error.message || __("Employee policy is not configured.")));
};
