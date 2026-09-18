# Read-only audit prompts

Source-only review briefs. Each was used to drive a locked-down read-only agent
against this app repository; findings live in `../audit_findings_2026-09-17.md`.

| File | Scope |
| --- | --- |
| `AUDIT_HANDOFF.md` | Full delivery-plan review against actual app code (implementation slices + false-ready claims). |
| `AUDIT_DESK_ACCESS.md` | Daily usability, access control and people lifecycle. |
| `AUDIT_PAYROLL.md` | Payroll, attendance, leave and effective-dated rules. |

## `opencode.readonly.json`

A deny-by-default agent configuration used to run the audits: read/glob/grep/list
allowed, everything else (edit, bash, task, network, external directories)
denied, `.env` files excluded.

It is stored here rather than at the repository root **on purpose**. Placed at
the root it would silently apply to normal development sessions and block
editing and shell access. To run a locked-down audit, copy it into place for
that session only:

```bash
cp tasks/audits/opencode.readonly.json opencode.json   # activate
# ... run the audit in an isolated worktree ...
rm opencode.json                                       # deactivate
```

`opencode.json` is git-ignored, so the temporary activation is never committed.

A prompt is not a sandbox. These briefs tell the agent what *not* to do; the
permission block is what actually enforces it. Never point an unrestricted agent
at the live bench or site data.
