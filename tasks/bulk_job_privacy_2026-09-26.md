# Bulk job identity and result privacy — 2026-09-26

Parent: PR #36, `refactor/native-workspace-ia`, `fe2e62ce06997284d117b1c320cf46793da29086`.
Baseline: 609 passed, 0 skipped. Status: COMPLETE.

Installed Frappe `utils/background_jobs.py:execute_job` recursively retries
without forwarding `user`. A harmless synthetic job recorded its maker on the
first call and Administrator on retry. Native recursive cleanup also lost its
job context after successful retry. No business mutation was used in this probe.

Installed `realtime.publish_realtime` routes a message to `all` when given only
DocType, without user/docname/task. Native Shift and Leave bulk completion and
app SSA draft completion use that shape. The actual publisher reproduced room
`all` with a synthetic message and mocked Redis transport. Live Chromium reproduction also confirmed a Company-B Worker received the
Company-A native-shaped salary completion payload. All identifiers were synthetic.
The initial Socket.IO failure was local web startup without DEV_SERVER=1;
correcting the process environment and using the configured default site via
127.0.0.1 restored authenticated realtime without changing site credentials.

Mitigation uses supported `before_job`, native per-user rooms and a narrow native-call result adapter. Jobs must retain
their original enabled actor; missing identity fails before the job runs, rather
than guessing an identity or silently elevating to Administrator. Native mutation
loops, savepoints and queue thresholds remain unchanged.

The native publisher has no per-event hook. A narrow version-tested adapter changes
only the six bulk completion events appended by the wrapped native call in
Frappe's deferred realtime buffer, before returning to HTTP/job commit, to the
original operator's native user room. This buffer is an internal
v16 compatibility dependency, not claimed to be a public event API. Unknown
buffer shape or changed actor fails before commit. Tests exercise the real
publisher, native commit flush and native recursive worker executor. No core
function replacement, copied native bulk loop, new ledger or stored ACL.
App-owned SSA draft results use the public `user=` publisher argument directly.

The mixed native/custom Shift action restriction was separately reproduced.
It stays fail-closed for now: restoring native Schedule/Request actions needs
its own selected-record authorization proof in the final security pass, not a
role-only bypass hidden in this privacy patch.

No metadata/schema/DocPerm changes. Hook cache clear is required; no migration
or backup is required for Python-only hooks and callback changes. Final native bulk regressions: **8 passed**, 12 warnings. Live Chromium after-fix
proof: the Company-A maker received the synthetic completion and the unrelated
Company-B Worker received none. Both disposable identities were removed.
Caught native failures also discard their deferred messages so later unrelated
commits cannot broadcast partial results. Full suite: **613 passed, 0 skipped**, 86 warnings, 460.90 seconds.
Compileall, all 61 tracked JSON files and `git diff --check` passed. No JS/assets
changed. SOLJOB and prior campaign fixture markers have zero Users, User
Permissions, Has Role, Contacts, Employees or Employee-linked operational/pay
records remaining; native bulk fixtures assert their own exact cleanup. Queues
are empty. Production and real business records remain unchanged.
