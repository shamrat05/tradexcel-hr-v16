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
at `Desktop/tradex_hr_backup_20260918/bridge_clones_20260918/`. Secret scan of
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
