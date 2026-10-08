# SenseFace bridge integration contract (source audit, not device approval)

The standalone bridge stays in `shamrat05/SenseFace-HRMS-Bridge`. Its local
read-only checkout was clean on `main` at
`2cb9c50e2af2c0b995cd3e7d75185b98487d58e2` on 2026-09-26. The old
`c4839d5` audit below was accurate for its date but is superseded by this
source review. No bridge secrets, SQLite data or device commands were used.

| Function | Current bridge source | Workforce app source | Remaining evidence |
| --- | --- | --- | --- |
| ADMS receive | `/iclock/*` receives punches and stores them in SQLite; serials must be registered or explicitly allowed. ADMS terminals do not send an API key. | Biometric mapping is keyed by terminal serial and PIN. | Physical device/network restriction test. An asserted registered serial is not cryptographic device identity. |
| Punch import | `/api/v1/attendance` supports per-device cursor reads and requires a configured API key. `/health` also requires the key. | Packaged `workforce_suite.workforce_suite.biometric.worker` polls the bridge, records durable cursor/retry state and creates idempotent native Employee Checkins. | Deployed worker and physical delayed/replay tests. |
| Device configuration | Authenticated `POST /api/v1/devices/{serial}/configure` validates and stores a profile. It returns `applied_to_terminal: false` with manual Cloud Server Settings instructions. | `workforce_suite.api.push_device_configuration` sends that profile and stores bridge status on the native app device record. | Browser/device UAT must verify the manual terminal step. A stored bridge profile is not proof that a terminal changed settings. |
| Cross-device transfer | Authenticated `/api/v1/device-transfers` accepts an idempotency key and queues device commands. | App transfer API checks source/target records and uses a stable request key before creating the target PIN mapping. | Real terminal command/ack, retry and duplicate-delivery UAT. |

The current bridge source has request-size limits and registration checks.
Production still requires HTTPS, receiver network controls, off-box backup of
the separate bridge database, secret management, monitoring, and physical
device tests. Its local SQLite state must never be copied into this app.
