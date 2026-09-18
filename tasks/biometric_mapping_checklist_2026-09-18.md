# Section A — Biometric & device mapping: checklist

Tracking the nine items from the readiness register, with the reviewer's verdicts
reconciled against evidence. Status legend: **DONE** / **BLOCKED** / **ASK**.

Root finding that governs everything: the bridge worker resolves a punch with

```sql
-- sync/reliable_bridge_worker.py::_employee_map()
FROM `tabTradexcel Employee Biometric` a
JOIN `tabTradexcel Biometric Device` d ON d.name = a.device
WHERE a.enabled = 1 AND d.enabled = 1
  AND d.device_serial IS NOT NULL AND d.device_serial != ''
  AND a.biometric_id IS NOT NULL AND a.biometric_id != ''
-- then key = (device_serial, biometric_id); accepted ONLY if exactly one match
```

So the entire flow needs **`Tradexcel Employee Biometric` + a real device serial +
`enabled = 1` on both**. It does **not** read `Employee.attendance_device_id`.

End-to-end chain:

```
Device (ADMS; server address = ours) → bridge /iclock/cdata → SQLite `attendance`
  → worker polls /api/v1/attendance → key = (serial_number, PIN)
  → Tradexcel Employee Biometric → Employee Checkin → HRMS auto-attendance
```

---

## A1. Device serials blank, devices disabled — **DONE**

*Reviewer: confirmed.* Both Frappe devices had **blank `device_serial`** **and
`enabled = 0`**. The app deliberately refuses to assign a PIN without a serial.

Fixed: serials set to `NYU7251601170` (factory) and `NYU7254701931` (head office);
both enabled.

## A2. 221 mappings exist only in Selevo — **DONE**

*Reviewer: mostly confirmed — Selevo has 234 enrollment rows for 221 unique
employees; Frappe has zero.* Correct: 208 (factory) + 13 (head office) = **221
rows on the two live NYU devices**. The other 13 belong to the now-inactive
`tcl_ho` terminal and are not imported.

Verified before import: all 221 match a Frappe Employee via
`tradex_source_employee_id`, with **PIN identical in 221/221** cases and **zero
duplicate PINs** within either device (even when lowercased).

Imported into `Tradexcel Employee Biometric` with `source = "Selevo Import"` and
`source_reference` recording the Selevo employee id, so the lineage survives.

## A3. PINs are device-specific — **DONE (no action needed)**

*Reviewer: confirmed.* The doctype already keys on
`(device_serial, biometric_id)` via `assignment_key`, and the worker groups by the
same pair, treating a duplicate as ambiguous rather than guessing.

## A4. PIN casing inconsistent — **NOT PROVEN — downgraded**

*Reviewer: not proven; my earlier claim was overstated and I withdraw it.*

The inconsistency I saw was in **group prefixes** (`Cf` 15 vs `CF` 3, `Kl` 3 vs
`KL` 3), not in duplicate PINs. Re-checked on the two live devices:

| Device | PINs | Distinct | Distinct lowercased | Casing variants |
| --- | --- | --- | --- | --- |
| Factory | 208 | 208 | **208** | **none** |
| Head office | 13 | 13 | **13** | **none** |

All 221 PINs are distinct even after lowercasing, so there is **no matching
hazard today**. Left as-is rather than changing validation without evidence.

## A5. No per-device timezone field — **BLOCKED — needs your decision**

*Reviewer: confirmed.* No timezone field exists on the device doctype. The bridge
uses one global timezone, defaulting to `Asia/Dhaka`
(`SENSEFACE_TIMEZONE`, bridge `server.py:28`), and parses the device's
`event_time` as local.

**Why I am not implementing it:** adding the field requires a DocType change plus
`bench migrate`, and the repository's own `AGENTS.md` forbids an agent from
running migrations against the live site. I also cannot verify correctness
without a real punch.

**Residual risk:** if a terminal sends UTC while the bridge parses it as Dhaka,
every punch shifts by 6 hours and attendance is silently wrong.

## A6. Head-office device code is `admin@tradex.com` — **DONE**

*Reviewer: confirmed.* The docname is derived from `device_code`
(`autoname = field:device_code`), so this was a document rename. Safe at this
moment precisely because **no mapping rows existed yet**.

Renamed to `tcl_head_office`. The worker joins on `d.name`, and Frappe updates
link fields on rename, so nothing references the old name afterwards.

## A7. Old devices remain — **DONE (narrowed)**

*Reviewer: partly true — Selevo has inactive `tcl_ho`; Frappe has only two device
records and no `gate1`.* Agreed and corrected. In **Frappe** there was never a
`gate1` record; both of those terminals exist only in the Selevo dump.
`gate1` is `fbsy` (SDK-pull) and `tcl_ho` serial `AF5B201260063` is inactive, so
neither can push to us. Nothing to remove in Frappe; both remaining devices are
now enabled and carry real serials.

## A8. Unknown PINs silently dropped — **ASK**

*Reviewer: partly true — the worker records them as `unmapped`, so they are not
silent, but no Pending Frappe mapping is created.* Correct.

Current behaviour is safe: `process_punches()` sets status `unmapped` with reason
*"No unique Employee matches the biometric PIN"* and counts them, and the device
status becomes `Warning`. A punch is never mis-attributed.

**Why I am not implementing the auto-Pending mapping:** the logic lives in
`sync/reliable_bridge_worker.py`, which is **bench-level runtime and not in this
repository**, and it cannot be tested without a device. Also, auto-creating a
mapping for an unverified PIN risks linking a punch to the wrong person, which is
worse than a queue. This needs your decision.

## A9. Hardware replacement breaks mappings — **DONE (documented)**

*Reviewer: confirmed risk; no re-key procedure implemented.* Accepted.

Because `assignment_key = sha256(serial + PIN)`, replacing a terminal changes
every key for that device. The runbook is written in
`biometric_serial_swap_runbook_2026-09-18.md`. The safe procedure is:
retire the old serial, enrol on the new terminal, re-import the affected rows,
and never edit `device_serial` in isolation.

---

## NEW FINDING (not in the original list): the bridge worker could not create a single check-in — **FIXED**

Discovered while verifying the mapping by running the worker's own code path.
`sync/reliable_bridge_worker.py::_employee_map()` selects `a.name AS assignment`
and `a.employee`, so each map value is:

```
['assignment', 'biometric_id', 'company', 'device_serial', 'employee', 'employee_name']
```

but `_insert_checkin()` read `employee["name"]` at lines 231 and 236 — a key that
does not exist. Every punch therefore raised
`KeyError: 'name'` and was recorded as `failed`.

Corroborating evidence that it had never run successfully:

- the worker's state database (`sync/data/sync_state.sqlite3`) **did not exist** — it
  had never executed;
- all **22,293** `Employee Checkin` rows share a creation date of **2026-09-17**, a
  bulk import, not incremental worker output.

Fix applied (2 lines, exact diff):

```diff
-            (employee["name"], timestamp, device_id),
+            (employee["employee"], timestamp, device_id),
-            "doctype": "Employee Checkin", "employee": employee["name"],
+            "doctype": "Employee Checkin", "employee": employee["employee"],
```

Backup of the original: `sync/reliable_bridge_worker.py.bak-20260918-185728`.

### This fix is NOT version-controlled

`sync/` is **not a git repository**, so the correction lives only on this machine
and would be lost if the runtime is redeployed or replaced. This is the same
deployability gap already recorded as **H1** (runtime not in the repo). Until the
runtime is packaged into the app, the diff above is the authoritative record of
the change.

---

## Verification performed

1. The worker's own `_employee_map()` query returns **221 unique keys, 0
   ambiguous**.
2. `process_punches()` was exercised with the worker's real code path against
   sample PINs from the backup, with `insert_checkin` stubbed so **nothing was
   written** — every sampled punch resolved to the correct employee, 0 unmapped.

## What I cannot prove without the device

These are outside my reach and are **not** covered by the checks above:

- The terminal can reach the server address and authenticate (ADMS handshake).
- The bridge is running, reachable, and its `SENSEFACE_API_KEY` matches.
- Punch timestamps land in the right timezone (A5).
- HRMS turns the resulting `Employee Checkin` rows into `Attendance` correctly at
  scale.

Items A1–A4, A6, A7 and A9 are done. A5 and A8 are open and need you.
