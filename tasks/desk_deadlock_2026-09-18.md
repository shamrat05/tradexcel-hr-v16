# "Deadlock Occurred" on the Workforce Suite desk — 2026-09-18

## Symptom

Browsing `/app/workforce-suite` intermittently showed:

```
Deadlock Occurred
Server failed to process this request because of a concurrent conflicting request. Please try again.
```

It stopped on its own and did not reproduce once only one client was active.

## What the message actually is

The dialog is Frappe's client-side handler for `QueryDeadlockError`
(`frappe/public/js/frappe/request.js`, `exception_handlers.QueryDeadlockError`).
The server raises that error for **two different MariaDB conditions**
(`frappe/database/mariadb/database.py`):

```python
def is_deadlocked(e) -> bool:
	# Snapshot isolation is also treated as deadlock from User POV
	return e.args and e.args[0] in (ER.LOCK_DEADLOCK, ER.CHECKREAD)
```

| Constant | Code | Meaning |
| --- | --- | --- |
| `ER.LOCK_DEADLOCK` | 1213 | genuine InnoDB deadlock |
| `ER.CHECKREAD` | **1020** | "record has changed since last read" — snapshot invalidation |

`ER.LOCK_WAIT_TIMEOUT` (1205) is separate and shows a different dialog
("Request Timeout"), so this was not a lock-wait timeout.

This host runs `REPEATABLE-READ`, which is the isolation level where `CHECKREAD`
appears: a transaction's read view becomes inconsistent because another
transaction committed changes to rows it had already read. Frappe deliberately
presents that to the user as a deadlock.

## Why it happened here

`ER.CHECKREAD` needs **two clients writing overlapping rows at the same time**.
During the window in question there were exactly that:

- the user's own Chrome session on the desk, and
- several automated headless Chromium sessions plus CLI connections driven by
  the agent against the same site.

Both were authenticated as **`Administrator`**, so they contended on the *same*
rows. Frappe writes to those rows from `Session.update()`
(`frappe/sessions.py`):

```python
(frappe.qb.update(Sessions).where(Sessions.sid == self.data["sid"])
   .set(Sessions.sessiondata, ...).set(Sessions.lastupdate, now)).run()

frappe.db.set_value("User", frappe.session.user, "last_active", now, update_modified=False)
frappe.db.commit()
```

So every session write touches `tabSessions` *and* the session user's
`tabUser` row. Two `Administrator` sessions therefore write the same `tabUser`
row, and the Workforce Suite workspace fires a burst of parallel requests (6 number
cards, 7 charts, reports), each its own transaction — plenty of opportunity for
one transaction's commit to invalidate another's read view.

It stopped when the automated sessions stopped. That is consistent with the
above and is the reason the agent now avoids driving the desk concurrently.

## Why there was no trace to inspect

- `SHOW ENGINE INNODB STATUS` showed no `LATEST DETECTED DEADLOCK` section.
- `innodb_print_all_deadlocks` is **0** on this host, so nothing was written to
  the MariaDB error log.
- The site's database user (`hrms_db`) has only `GRANT ALL ON hrms_db.*`, no
  `SUPER`, so it cannot change that setting. A root user must run:

```sql
SET GLOBAL innodb_print_all_deadlocks=1;   -- add to config to persist
```

## Prevention

1. **Never drive the live desk with automated browsers while the user is using
   it.** Serialize; ask first.
2. **Use a dedicated automation user**, not `Administrator`. Distinct users
   write distinct `tabUser` rows, which removes the shared-row collision.
3. **Never mint or delete `tabSessions` rows while the site is under load** — the
   server writes the same rows concurrently.
4. Turn on `innodb_print_all_deadlocks` so any recurrence is diagnosable.
5. For Contabo, serve through a real WSGI setup with multiple workers rather than
   `bench serve`; Frappe's own retry handling applies per request.

## Not changed

No application code was changed for this. The desk's retry path
("Please try again.") is Frappe's intended behaviour for a transient conflict.
Only documentation and an agent behaviour rule were added.
