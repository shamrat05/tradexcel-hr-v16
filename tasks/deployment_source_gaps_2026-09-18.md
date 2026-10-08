# Deployment source gaps — 2026-09-18

Findings from verifying that the running site matches the committed source. No
changes were made to the site; this records gaps only.

## Finding 1 — seven reports exist only in the database

`tabReport` contains twelve reports whose module is `Workforce Suite`, but the
repository defines only five of them as source:

| Report | `is_standard` | In git? |
| --- | --- | --- |
| Biometric ID Audit | Yes | ✅ |
| Daily Attendance Summary | Yes | ✅ |
| Employee Data Gaps | Yes | ✅ |
| Workforce Salary Coverage Board | Yes | ✅ |
| Workforce Anomaly Radar | Yes | ✅ |
| Workforce Daily Attendance Board | **No** | ❌ |
| Workforce Joiners and Leavers | **No** | ❌ |
| Workforce Leave Balance Board | **No** | ❌ |
| Workforce Pay Component Register | **No** | ❌ |
| Workforce Payroll Register | **No** | ❌ |
| Workforce Payroll Variance | **No** | ❌ |
| Workforce Shift Coverage | **No** | ❌ |

`is_standard = No` means the report was created through the Desk UI rather than
loaded from app source, so it lives in the database alone.

### Why this matters for a Contabo deploy

**All seven are referenced by the committed workspace layout**
(`workforce_suite/workforce_suite/workspace/workforce_suite/workforce_suite.json`). A fresh
install from this repository — which is what a deploy does — creates the
Workforce Suite workspace with shortcuts pointing at reports that do not exist. The
Action Board renders dead links.

This is the failure mode the source-only AGENTS.md rules already warn about from
the other direction: runtime truth that is not reproducible from source.

### Verify

```bash
bench --site hrms.localhost mariadb -e \
  "select name, is_standard from tabReport where module='Workforce Suite' order by name;"

rg -F 'Workforce Payroll Register' \
  apps/workforce_suite/workforce_suite/workforce_suite/workspace/workforce_suite/workforce_suite.json
```

## Finding 2 — three orphaned report folders

These directories are tracked in git but contain only an `.html` file — no
`.json`, `.py` or `.js`, and no `__init__.py`:

```
workforce_suite/workforce_suite/report/workforce_daily_attendance_board/   (html only)
workforce_suite/workforce_suite/report/workforce_leave_balance_board/      (html only)
workforce_suite/workforce_suite/report/workforce_payroll_register/         (html only)
```

The corresponding report names appear in `tabReport` as non-standard, so these
look like the print templates of reports that were later recreated through the
UI. As source they are inert and misleading.

## Recommended resolution (not applied)

For each of the seven, decide one of:

1. **Promote to source** — add `<name>.json`, `.py`, `.js` and the print `.html`
   under `workforce_suite/workforce_suite/report/<name>/` and set `is_standard`. Then the
   desk link is reproducible from a clean checkout. Preferred, because the deploy
   target starts from an empty database and has nothing to inherit.
2. **Remove from the workspace and the database** if the report is not wanted.

Either way, do not hand-copy definitions out of a production database without
review, and do not run a migration to "fix" this: the gap is in version control,
not in the schema.

## Status

- No report definition was created, exported, modified or deleted.
- No migration was run. None is required for the commits merged today — those
  touched no DocType JSON, and the workspace `content` in the database is
  byte-identical to the committed JSON.
- This is a documented blocker for "clone to Contabo and it works", nothing more.
