# Site settings and demo data — 2026-09-18

## 1. Help menu trimmed (applied)

**Change:** hid six items from the Desk Help dropdown, keeping only
`Keyboard Shortcuts`.

| Help item | Before | After |
| --- | --- | --- |
| Documentation | visible | hidden |
| User Forum | visible | hidden |
| Frappe School | visible | hidden |
| Report an Issue | visible | hidden |
| About | visible | hidden |
| **Keyboard Shortcuts** | visible | **visible** |
| Frappe Support | visible | hidden |

**Mechanism.** ERPNext seeds these as `Navbar Item` rows
(`parenttype = "Navbar Settings"`, `is_standard = 1`) in
`erpnext/setup/install.py`. Frappe renders only items whose `hidden` is falsy:

```jinja
{# frappe/public/js/frappe/ui/toolbar/navbar.html #}
{% if (!item.hidden) { %}
```

`NavbarSettings.validate()` also forbids deleting standard items
(*"Please hide the standard navbar items instead of deleting them"*), so the six
rows were set to `hidden = 1`. **Nothing was deleted.**

**Verified** in the rendered boot payload — visible items are:
`['Keyboard Shortcuts']`.

**Gotcha for future queries:** `Navbar Settings` is a Single DocType. Its values
live in `tabSingles` (`doctype = 'Navbar Settings'`) and its items in
`tabNavbar Item`. There is deliberately **no** `tabNavbar Settings` table, so a
query against that name fails.

`bootinfo` cache was cleared so the change appears without a server restart.

## 2. Demo data — investigation only, nothing deleted

Demo data **is still present**. Only the demo *company* is missing.

| Kind | Records present | Names |
| --- | --- | --- |
| Customer | 3 | Grant Plastics Ltd., West View Software Ltd., Palmer Productions Ltd. |
| Supplier | 3 | Zuckerman Security Ltd., MA Inc., Summit Traders Ltd. |
| Item | 10 | T-shirt, Laptop, Book, Smartphone, Sneakers, Coffee Mug, Television, Backpack, Headphones, Camera |
| Item Group | 1 | Demo Item Group |
| Customer Group | 1 | Demo Customer Group |
| Supplier Group | 1 | Demo Supplier Group |
| Sales Order | 5 | `SAL-ORD-2026-00001` … `00005`, all `docstatus = 1` |
| Purchase Order | 10 | `PUR-ORD-2026-00001` … `00010`, all `docstatus = 1` |

These match the ERPNext fixtures in
`erpnext/setup/demo_data/*.json` exactly (3 customers, 3 suppliers, 10 items,
5 sales orders, 10 purchase orders), so they are generated demo records rather
than real data.

### Why "Clear Demo Data" fails

`erpnext/setup/demo.py`:

```python
@frappe.whitelist()
def clear_demo_data():
	...
	company = frappe.db.get_single_value("Global Defaults", "demo_company")  # "Shamrat (Demo)"
	create_transaction_deletion_record(company)   # <-- raises here
	clear_masters()
	delete_company(company)
	except Exception:
		frappe.db.rollback()
		frappe.throw(_("Failed to erase demo data, please delete the demo company manually."),
		             title=_("Could Not Delete Demo Data"))
```

`Global Defaults.demo_company = "Shamrat (Demo)"`, but `tabCompany` contains
only `Tradexcel Ceramics Ltd.` and `Elegance Footwear Ltd.`. The demo company was
removed at some point without running the cleanup, so
`create_transaction_deletion_record("Shamrat (Demo)")` cannot resolve the company
and the whole transaction rolls back.

**Consequence:** the 15 demo orders are *submitted* documents whose `company`
link points at a company that no longer exists — dangling links that no longer
appear in the Company list.

### Related stale setting

`Global Defaults.default_company = "Shamrat"` — also a company that no longer
exists. It is currently harmless because the effective default comes from
`tabDefaultValue.company = "Tradexcel Ceramics Ltd."`, but it should be cleaned
up alongside.

### Options

| Option | Approach | Trade-off |
| --- | --- | --- |
| A | Recreate `Shamrat (Demo)`, then use the official button | Uses the supported path and a Transaction Deletion Record for accounting correctness. But the orphaned orders' accounts/GL no longer exist, so the deletion tasks may still fail; recreating a company is itself heavy. |
| B | Manual targeted cleanup: cancel + delete the 15 orders, delete the 6 demo masters, clear `Global Defaults.demo_company` | Direct and predictable. Needs a **backup first**; cancelling submitted docs can fail if ledger entries reference removed accounts. |
| C | Leave the records, clear only the stale pointer | Stops the button from erroring, but the demo masters and orders remain. |

**Recommendation:** take a site backup, then Option B. The site is not using
ERPNext sales/purchase at all, and these are the *only* items, customers and
suppliers present, so there is nothing real interleaved with them.

## Removal — executed 2026-09-18

**Backup first.** `bench --site hrms.localhost backup --with-files` produced a
2.8 MiB database dump plus public/private files, mirrored to
`Desktop/tradex_hr_backup_20260918/site_backup_before_demo_removal/`.

**Frappe's own path was proven impossible before touching data.** A trial
(cancelled and rolled back) showed every doctype refuses to cancel, because the
company's warehouses and accounts were destroyed with it:

| Doctype | Cancel result |
| --- | --- |
| Payment Entry | `TypeError: cannot unpack non-iterable NoneType` |
| Sales Invoice | `LinkValidationError: Could not find Warehouse: Finished Goods - SD, Company: Shamrat (Demo)` |
| Purchase Invoice | `LinkValidationError: Could not find Warehouse: Goods In Transit - SD, Company: Shamrat (Demo)` |
| Sales Order | `LinkExistsError` — linked Sales Invoice |
| Purchase Order | `LinkExistsError` — linked Purchase Invoice |

So the removal was surgical and **metadata-driven** — child tables are
enumerated from `frappe.get_meta(dt).get_table_fields()` rather than hardcoded,
so it stays correct as doctypes change.

Deleted, in dependency order:

| Stage | Removed |
| --- | --- |
| Submitted transactions | Payment Entry 5, Sales Invoice 5, Purchase Invoice 6, Sales Order 5, Purchase Order 10 (**31 docs**, plus their child tables) |
| Ledger rows for the phantom company | GL Entry 42, Payment Ledger Entry 16, Stock Ledger Entry 16 (Repost Item Valuation 0) |
| Demo masters | Customer 3, Supplier 3, Item 10, plus `Demo Item Group`, `Demo Customer Group`, `Demo Supplier Group` |
| Stale pointers | `demo_company` → empty, `default_company` `Shamrat` → `Tradexcel Ceramics Ltd.` |

**Verified after:**

| Check | Result |
| --- | --- |
| Transactions under the phantom company | 0 |
| Ledger rows under the phantom company | 0 |
| Documents named like `%Demo%` | 0 |
| Global Defaults | `demo_company` empty, `default_company = Tradexcel Ceramics Ltd.` |
| `tabDefaultValue.company` | `Tradexcel Ceramics Ltd.` (now consistent with the above) |
| Real data | 2 companies, 241 Employees, 10 Warehouses — unchanged |
| Site health | `/login` 200, `/api/method/ping` 200, no error-log entries |

### The dialog is now gone at the source

`erpnext/public/js/utils/demo.js` renders the menu item only when the pointer is
truthy:

```js
$(document).on("toolbar_setup", function () {
	if (frappe.boot.sysdefaults.demo_company) {   // now empty
		render_clear_demo_action();
	}
});
```

With `demo_company` cleared, `frappe.defaults.get_defaults()` returns `None` for
it, so **"Clear Demo Data" no longer appears at all** — the failure cannot
recur. Caches were flushed (`clear-cache`, `clear-website-cache`) so boot picks
up the new value without a server restart.

### Note on `default_company`

It previously read `Shamrat`, a company that does not exist — a latent bug that
would surface wherever `Global Defaults.default_company` is consulted. It is now
set to `Tradexcel Ceramics Ltd.`, matching the effective `tabDefaultValue.company`.
