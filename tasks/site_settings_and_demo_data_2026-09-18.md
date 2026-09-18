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

## Not done

No document was cancelled, deleted or modified. No backup was taken. The only
change applied in this session is the Help-menu visibility above.
