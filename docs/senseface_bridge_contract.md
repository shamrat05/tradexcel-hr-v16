# SenseFace bridge integration contract (audit, not go-live approval)

Source: private `shamrat05/SenseFace-HRMS-Bridge`, inspected at commit `c4839d5f4016072dded72a0f009049f145b59690` on 2026-09-17. Keep the standalone listener separately versioned and backed up; never put its SQLite database or API key in this app repository.

| Function | Bridge at pinned commit | Tradexcel HR currently |
| --- | --- | --- |
| ADMS receive | `/iclock/cdata`, `/iclock/getrequest`, SQLite durability | Device must point to the listener hostname; no actual device test in this audit |
| Punch import | `GET /api/v1/attendance?after_id=...&serial_number=...`; API key enforced only when configured | Bench-local `sync/reliable_bridge_worker.py` polls per device; worker is **not packaged in this app** |
| Device configuration | No `/api/v1/devices/{serial}/configure` endpoint | `tradex_hr/api.py:push_device_configuration` calls that missing endpoint; Frappe's Configure button fails |
| Cross-device people | Bridge stores device serial + local PIN | Frappe must map `(serial, PIN)` to one canonical Employee; sync user template to another device is a separate command/consent flow |

Safety findings: the device-facing `/iclock/*` receiver accepts an asserted serial number and has no per-device authentication; the API key protects `/api/v1/*` reads only when configured. `/health` exposes device metadata. Do not put this listener on a public Contabo endpoint as-is and call it hardened. Require a tested HTTPS reverse proxy, restricted receiver exposure where feasible, request-size/rate controls, secret management, monitoring and backup/restore. Decide how legitimate devices authenticate or are network-restricted before enabling remote configuration commands.

Next verified slice: write failing bridge tests for authorized configuration, unknown serial, duplicate/replayed command, unsafe payload, unreachable device, and persistence/retry. Define the ADMS command/ack protocol from actual device behavior; only then add the endpoint and connect the Frappe button. Separately package the Frappe worker into this app and prove two-device cursor replay, no duplicate Employee Checkins, ambiguous PIN quarantine, and cross-branch attendance attribution. A successful `/health` response is not proof of delivery to Frappe.
