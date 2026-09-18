# Runbook: replacing a biometric terminal (serial swap)

Because a mapping key is derived from hardware, replacing a terminal is a
data-affecting operation, not a plug-and-play swap.

## Why it breaks

`TradexcelEmployeeBiometric.validate()` computes

```python
self.assignment_key = sha256(f"{serial}\0{biometric_id}")
```

and the bridge worker resolves punches by `(device_serial, biometric_id)`.
So a new serial means **every existing key for that device becomes unreachable** —
the terminal would push punches that match no employee, and they would all be
queued as `unmapped`.

## What is safe

- **Renaming** a device (`device_code`) is safe — it is the docname, and Frappe
  updates links. The worker joins on `d.name` and matches on `device_serial`.
- **Changing `device_name` / `company` / `bridge_url`** is safe.

## Procedure

1. **Do not edit `device_serial` in place and stop there.** That orphans every
   mapping already issued for that device.
2. Record the current state first:
   ```sql
   SELECT d.device_code, d.device_serial, COUNT(*) AS mappings
     FROM `tabTradexcel Employee Biometric` a
     JOIN `Tradexcel Biometric Device` d ON d.name = a.device
    WHERE d.device_code = '<device>'
    GROUP BY d.device_code, d.device_serial;
   ```
3. Decide per terminal:
   - **Same employees move to the new terminal** → update the device's
     `device_serial` **and re-save every mapping for that device** so the keys are
     recomputed. The mapping rows keep their `employee`; only the derived serial
     and key change.
   - **Both terminals run in parallel for a transition** → create a *second*
     device record for the new serial and issue its own mappings, rather than
     repointing the old one. Both then attribute independently.
   - **Terminal retired** → disable it (`enabled = 0`). The worker filters on
     `d.enabled = 1`, so its mappings go quiet without being deleted.
4. Re-import from the device's own pushed user list (the bridge stores it in the
   `senseface_employees` equivalent), not from memory — the terminal is the source
   of truth for what it has enrolled.
5. **Verify before trusting it:**
   ```sql
   SELECT COUNT(*) FROM `tabTradexcel Employee Biometric` a
     JOIN `Tradexcel Biometric Device` d ON d.name = a.device
    WHERE d.enabled = 1 AND d.device_serial = '<new serial>';
   ```
   and confirm the worker's resolver returns one key per PIN with none ambiguous.

## Guard rails already in place

- The DocType **refuses** a duplicate `(serial, PIN)` — a re-point cannot silently
  produce two employees on the same PIN.
- The worker treats an ambiguous `(serial, PIN)` as `unmapped` rather than
  guessing, so a botched swap yields a visible queue, not wrong payslips.
- `enabled` on both the device and the mapping is required, so a half-finished
  swap stays inert instead of half-working.

## Related

- `tasks/biometric_mapping_checklist_2026-09-18.md` — Section A status.
- Device `device_code` is the docname (`autoname = field:device_code`); renaming is
  a document rename, so do it while no mappings reference the device, or accept
  that Frappe will rewrite the links.
