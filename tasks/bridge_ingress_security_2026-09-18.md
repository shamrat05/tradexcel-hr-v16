# Bridge launcher and ingress security — 2026-09-18

## The problem in one line

`start_biometric_bridge.bat` runs the bridge from `Desktop\Projects\SenseFace-HRMS-Bridge`,
which is **neither** the hardened branch **nor** a committed state — it was 789
lines of uncommitted work whose read APIs were open to anyone.

## What was actually on disk

Both folders clone the same repo (`shamrat05/SenseFace-HRMS-Bridge`) but had
diverged:

| | `Projects/` — **what runs** | `Desktop/` |
| --- | --- | --- |
| Branch | `main` (`c4839d5`), 17 dirty files | `fix/bridge-ingress-hardening`, 6 dirty |
| `server.py` | **789** working / 327 committed | 439 |
| Unpushed commits | 0 | 3 |

The `Projects/` working tree held **+726/−264 lines of uncommitted `server.py`**
plus untracked modules that appear to anticipate hosting: `configure_device.py`,
`device_config.py`, `transfer.py`, `Dockerfile`, `docker-compose.yml`,
`deploy/nginx/attendance.conf`, `CONTABO.md`, `.env.example`.

Neither lineage was a superset:

| Control | `Projects/` (running) | `Desktop/` (hardened) |
| --- | --- | --- |
| `/configure` endpoint | ✅ | ✅ |
| device registration | ✅ | ✅ |
| metadata preservation | ✅ | ✅ |
| **API key fails open** | **❌ open** | ✅ closed |
| **constant-time compare** | **❌** | ✅ |
| **bounded body size** | **❌** | ✅ |
| **/health authenticated** | **❌** | ✅ |

So repointing the launcher at `Desktop/` would have been wrong — it would have
replaced the richer implementation with an older, smaller one.

## A correction to the earlier finding

An earlier scan reported "device registration enforced: YES" in the running
bridge. **That was a false positive** — it matched imports such as
`from device_config import device_profile, validate_serial`, not enforcement. The
`/iclock/cdata` handler took `SN` straight from the query string and wrote it
with no check against any registry. The bridge's `devices` table was **empty**,
so there was also nothing to check against.

## Work done

### 1. Preserved both uncommitted states (nothing lost)

```
wip/preserve-uncommitted-20260918      adf1f19  (Projects/ working tree)
wip/preserve-hardening-clone-20260918  b699333  (Desktop/ working tree)
```

Both pushed. Full mirrors plus all-refs bundles and uncommitted patches also sit
at `Desktop/workforce_suite_backup_20260918/bridge_clones_20260918/`. Secret scan of
both patches: clean. `data/senseface_hrms.db` (the attendance store) was already
git-ignored and was not committed.

### 2. Closed the ingress gaps in the code that runs

| Fix | Before | After |
| --- | --- | --- |
| `authorized()` | `not API_KEY or header == API_KEY` — **open when unset** | `bool(API_KEY) and hmac.compare_digest(...)` — fails closed |
| `/health` | unauthenticated; disclosed device serial/IP | requires the API key |
| Body size | `int(Content-Length)` unbounded | `MAX_BODY_BYTES` (1 MiB) → 413; absent/non-numeric → 411 |
| Asserted serial | trusted verbatim | `SENSEFACE_ALLOWED_SERIALS` → 403 for unknown terminals |
| `.env` | shipped `.env.example`, read no `.env` | stdlib `KEY=VALUE` loader; real env vars still win |

The `.env` loader is stdlib-only because `python-dotenv` is not installed in
either Python on this machine, and the bridge's style is dependency-free.

A generated key was written to `Projects/.env` (mode 600, git-ignored).
`SENSEFACE_ALLOWED_SERIALS` is set to the two real NYU serials.

### 3. Verified

Against an **isolated** instance (temp data dir, port 8199) — the real bridge was
never started:

| Case | Result |
| --- | --- |
| `GET /api/v1/attendance`, no key | **401** |
| `GET /api/v1/attendance`, wrong key | **401** |
| `GET /api/v1/attendance`, correct key | **200** |
| `GET /health`, no key | **401** |
| `POST /iclock/cdata` claiming 8 MiB | **413** |
| Content-Length genuinely absent (raw socket) | **411** |
| Content-Length non-numeric (raw socket) | **411** |
| `POST /iclock/cdata` from a spoofed serial | **403** |
| `POST /iclock/cdata` from a known serial | **200**, `OK: 1` |

One check initially "failed" — my *test* was wrong: `http.client` always emits
`Content-Length: 0`, so it cannot express an absent header. Re-tested with a raw
socket, which confirmed 411. The code was correct; the corrected suite reports
**ALL PASS**.

## What must still happen before a terminal is pointed at this

1. **Decide the canonical bridge.** Two lineages exist. The running one is
   richer; the hardened one is more secure. They need merging deliberately, not
   by repointing the launcher.
2. **Merge the ingress fixes into a reviewed branch** rather than leaving them as
   a WIP checkpoint on top of unreviewed work.
3. **Set `SENSEFACE_API_KEY` for the real launch.** The `.env` is in place, but
   nothing verifies it is loaded outside the isolated test.
4. **TLS / reverse proxy.** The bridge binds `0.0.0.0:8090` by default. The
   `deploy/nginx/attendance.conf` exists but is untested.
5. **The bridge cannot authenticate a device itself.** ADMS terminals do not send
   an API key on `/iclock/*`, so the serial allowlist is the only control there.
   Network restriction (the file itself warns the listener must not face the
   public internet) is still required.
6. **Timezone** — `SENSEFACE_TIMEZONE=Asia/Dhaka` is now explicit; it still needs
   confirming against a real punch.

## Repo state

| Repo | Branch | HEAD | Dirty |
| --- | --- | --- | --- |
| `Projects/SenseFace-HRMS-Bridge` | `wip/preserve-uncommitted-20260918` | `de40695` | 0 |
| `Desktop/SenseFace-HRMS-Bridge` | `wip/preserve-hardening-clone-20260918` | `b699333` | 0 |

Both clean, everything pushed. `*.bak-*` was added to `.gitignore` and the
`server.py` backup was moved out of the repo into the backup folder.


---

# Which lineage is canonical — decided, with evidence

## Decision: `Desktop\Projects\SenseFace-HRMS-Bridge` is the base

Compared by function surface, not by line count:

| Capability | `Projects/` | `Desktop/` (hardened) |
| --- | --- | --- |
| `/configure`, device profiles | yes | no |
| backup export / request / restore | yes | no |
| device transfer (+ plan) | yes | no |
| command queue (enqueue, remap PIN, query, response) | yes | no |
| raw-request parsing helpers | yes | no |
| `registered_serial()` enforcement | was missing | yes |
| `BoundedThreadingHTTPServer` | was missing | yes |

The hardened clone is **complementary, not superior**: it holds two controls the
richer implementation lacked, and lacks a dozen features the richer one has.
That is why repointing the launcher would have been wrong.

## The two missing controls are now ported

`server.py` is 904 lines and has both, so the running copy is now a superset.

**`registered_serial(serial)`** — a terminal is known when an operator configured
it (a row in `device_profiles`) or when it is listed in
`SENSEFACE_ALLOWED_SERIALS`; otherwise `/iclock/cdata` returns 403 instead of
trusting the caller-supplied `SN`.

Implemented against the **existing `device_profiles` table**, so no schema change
and no migration. The hardened clone used a `registered` column on `devices`,
which this schema does not have — the profile table is the accurate equivalent
here and is what `/configure` already writes.

**`BoundedThreadingHTTPServer`** — caps concurrent request threads
(`SENSEFACE_MAX_CONCURRENT_REQUESTS`, default 64).

## Verified: the full onboarding lifecycle

| Step | Result |
| --- | --- |
| Unregistered serial pushes | **403** |
| Configure it via `/api/v1/devices/<sn>/configure` (with the key) | **200**, profile stored |
| The same serial pushes again | **200** — registered dynamically, no `.env` edit |
| Configure without the API key | **401** |

This is the intended flow: **configure the terminal in Frappe → the bridge
registers it → its punches are accepted.** The `SENSEFACE_ALLOWED_SERIALS` list
in `.env` is the fallback for the two existing NYU terminals, so they work
before anyone configures them.

Also re-confirmed: the bridge's own `test_device_config.py` and
`test_transfer.py` pass (8 passed), and the security suite is ALL PASS.


---

# Promoted to main — 2026-09-18

`Projects/SenseFace-HRMS-Bridge` is now on **`main`** (`2cb9c50`), clean, with
`server.py` at 904 lines. `main` was `c4839d5` (327 lines, open read API, no
device configuration, no limits, no registration check); it now carries the
implementation that runs plus the ported hardening.

Merged with `--no-ff` so the promotion is a dated, identifiable event:

```
* 2cb9c50 Merge the canonical bridge into main
* f30a3da docs: make the bridge configurable and safe to onboard from the README
* a97206b feat(security): enforce device registration and bound concurrency
* de40695 chore: ignore editor/backup artefacts
* 673bb77 fix(security): close the ingress gaps in the running bridge
* adf1f19 chore: preserve uncommitted bridge work
```

`start_biometric_bridge.bat` is **unchanged** and now correct: it already pointed
at `Desktop\Projects\SenseFace-HRMS-Bridge`, which is the canonical checkout.

## Repo made self-documenting

`.env.example` documented 4 settings while the code read 11, so a fresh
deployment could not be configured correctly. It now documents all of them -
verified programmatically as `documented == read`, with no gaps and no unused
entries - and states that `SENSEFACE_API_KEY` is required because the bridge
fails closed.

The README gains **Required configuration**, **Security posture** and
**Onboarding a terminal**, including the non-obvious point that `/iclock/*`
cannot use an API key (ADMS terminals send no headers) and is therefore protected
by device registration instead.

## Verified on the merged tree

- security suite from `main`: **ALL PASS** (401 / 413 / 403 / 200 as expected)
- the bridge's own `test_device_config.py` + `test_transfer.py`: **8 passed**
- `wip/preserve-uncommitted-20260918` confirmed an ancestor of `main`, so nothing
  was dropped in the promotion

## A mistake worth recording

The first merge attempt failed on **no git identity** (the individual commits had
used `-c user.name=...`, but `git merge` did not). The `git checkout main` that
preceded it had already removed the new modules from the working tree, so for a
moment the on-disk bridge was the old 327-line version. It was detected by the
verification step, fixed by setting a repo-local identity and completing the
merge, and confirmed whole afterwards. Run the verification after a branch
switch, not before it.
