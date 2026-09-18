# Checkout consolidation — 2026-09-18

Execution report for consolidating the Tradexcel HR working trees onto a single
canonical checkout, and removing the false-diff that had been masking real state.

## Problem found

Two independent clones of `shamrat05/tradexcel-hr` existed and had diverged:

| Clone | Path | HEAD before | Reported dirty |
| --- | --- | --- | --- |
| Windows mirror | `/mnt/c/Users/Sanchita/Desktop/tradexcel-hr-audit-app` | `93e66ad` (`main`) | 78 files, 4 untracked |
| WSL bench | `/home/sanchita/frappe-bench/apps/tradex_hr` | `2c45bb2` (`fix/device-rpc-authorization`) | 2 files, 2 untracked |

Three risks fell out of this:

1. **The Windows "78 modified files" were entirely fictitious.** `git diff`
   reported 7038 insertions and 7038 deletions, and every file had *identical*
   add/delete counts (`912/912`, `416/416`, …) — the signature of a line-ending
   flip. `git diff --ignore-cr-at-eol` and `git diff --ignore-all-space` both
   returned **empty**: zero real content change.
2. **Real work existed only on one disk.** Commits `557d4a8` and `2c45bb2` sat on
   the unpushed local branch `fix/device-rpc-authorization`, which had no remote
   tracking. `main` (`93e66ad`) contained none of it.
3. **The Windows clone was not the runtime.** `~/frappe-bench/sites/apps.txt`
   lists `tradex_hr`, so Frappe loads the WSL bench directory only. Edits in the
   Windows tree could never affect the running app.

## Actions taken

1. **Backup before any change.** Created a verified bundle of the full bench
   repository plus copies of the four Desktop-only files:
   `Desktop/tradex_hr_backup_20260918/` (bundle v2 format; `git bundle verify`
   reported *"records a complete history"*). Pre-change HEADs recorded in
   `bench_HEAD_before.txt` / `desktop_HEAD_before.txt`.
2. **Rescued the four Windows-only files into the canonical tree.** Three were
   read-only audit briefs and one was the deny-by-default audit agent profile.
   All four verified byte-identical with `cmp`:

   | Rescued file | Destination |
   | --- | --- |
   | `AUDIT_HANDOFF.md` | `tasks/audits/AUDIT_HANDOFF.md` |
   | `AUDIT_DESK_ACCESS.md` | `tasks/audits/AUDIT_DESK_ACCESS.md` |
   | `AUDIT_PAYROLL.md` | `tasks/audits/AUDIT_PAYROLL.md` |
   | `opencode.json` | `tasks/audits/opencode.readonly.json` |

   The read-only profile was stored under `tasks/audits/` rather than the
   repository root on purpose: at the root it would silently deny `edit` and
   `bash` for ordinary development sessions. `tasks/audits/README.md` documents
   how to activate it for an audit and remove it afterwards.
3. **Pinned line endings.** Added `.gitattributes` with `* text=auto eol=lf` and
   explicit `binary` markers. Verified beforehand that the index contained **zero**
   CRLF files, so this triggered no re-normalisation churn.
4. **Stopped the phantom diff recurring.** Added `opencode.json` / `opencode.jsonc`
   to `.gitignore` so a temporary read-only profile can never be committed.
5. **Recorded the canonical checkout** in `AGENTS.md`, together with the rule that
   an all-files-modified status with equal insert/delete counts is a CRLF artifact
   to be confirmed with `git diff --ignore-cr-at-eol`.
6. **Committed and pushed.** Branch `fix/device-rpc-authorization` now tracks
   `origin/fix/device-rpc-authorization`; the three commits are no longer
   single-disk.
7. **Rendered the Windows clone harmless.** Restored its working tree from HEAD
   (removing only CRLF differences), moved it onto the same branch and commit as
   the canonical tree, added `README_DO_NOT_EDIT_HERE.md`, and excluded local
   mirror signage via `.git/info/exclude` so it always reports clean.

## Verified end state

```
bench   HEAD : aad6a5b  (fix/device-rpc-authorization, tracks origin)
mirror  HEAD : aad6a5b  (same commit, clean status, LF only)
```

- Both trees at the same commit; no pending work in either.
- No content deleted anywhere: the only removal was CRLF-only differences in the
  Windows mirror, proven empty by `--ignore-cr-at-eol` before restoring.
- Full history preserved in three places: WSL bench, GitHub, bundle backup.

## Opening the commit history

`git log` had shown a handoff note that predates this work. Notably, the secret
scan over the newly pushed commits returned **no secrets** — every `api_key` /
`password` / `token` hit was a variable name, a DocType field definition
(`bridge_api_key`, fieldtype `Password`) or prose warning about secrets.

## Contabo hosting readiness — flagged, not claimed

Nothing here constitutes a go-live readiness claim. Two blockers from the app's
own `AGENTS.md` and audit notes still stand and are directly relevant to hosting
on Contabo:

- The app checkout is **not yet deployable on its own**: verified payroll and
  biometric worker runtime/tests still live under the bench's `sync/` and must be
  packaged into app-owned modules first. Backup/restore rehearsal on a separate
  site and a clean-checkout install test remain open (Gate 0).
- The SenseFace bridge receiver **must not be exposed on a public Contabo
  endpoint as-is**: the `/iclock/*` receiver accepts an asserted serial with no
  per-device authentication, and `/health` discloses device serial/IP/count. It
  needs a tested HTTPS reverse proxy, secret management, request-size and rate
  limits, monitoring and backup before any cutover.

Both require owner decisions and staging verification; neither was changed here.
