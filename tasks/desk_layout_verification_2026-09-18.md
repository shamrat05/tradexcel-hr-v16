# Desk layout: measurement and fix — 2026-09-18

Record of a reported desk misalignment on `/app/tradexcel-hr`, the measurement
that found the cause, and the fix. Written because two rounds of reasoning
produced a wrong fix before measurement settled it.

## Symptom

The desk looked "out of sync": the ERPNext app logo floated well right of the
page head and sidebar, and the sidebar content read as slightly shifted.

## Method (reusable)

Guessing from SCSS did not resolve this. Measurement did. Two Playwright runs
against the same page, one with our stylesheet aborted at the network layer, one
without — then diff the geometry. No app files are touched.

```python
from playwright.sync_api import sync_playwright

# session sid minted via frappe.auth.LoginManager; see "Authentication" below
ctx.add_cookies([{"name": "sid", "value": SID, "domain": "localhost", "path": "/"}])
if block_our_css:
    ctx.route("**/tradexcel_desk.css*", lambda route: route.abort())
page.goto("http://localhost:8000/app/tradexcel-hr", wait_until="domcontentloaded")
page.wait_for_selector(".page-head")
# then compare getBoundingClientRect().x for each landmark
```

Playwright lives in the bench env: `/home/sanchita/frappe-bench/env/bin/python`
with chromium at `~/.cache/ms-playwright`. `developer_mode: 1` means
`app_include_css` is served by direct path, so **no `bench build` is needed** —
edit the CSS and reload.

### Authentication

The desk needs a session. `bench console` will not do because
`LoginManager.__init__` reads `frappe.local.request`. Minimal working recipe:

```python
import frappe
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

frappe.init(site="hrms.localhost", sites_path="/home/sanchita/frappe-bench/sites")
frappe.connect()
frappe.local.request = Request(EnvironBuilder(method="GET", path="/app").get_environ())
frappe.local.form_dict = frappe._dict()
frappe.local.response = frappe._dict()          # must support item assignment
from frappe.auth import LoginManager, CookieManager
frappe.local.cookie_manager = CookieManager()
LoginManager().login_as("Administrator")        # sets frappe.session.sid
```

The session created this way was deleted afterwards.

## Measurement (viewport 1600x900)

| Element | Stock Frappe | After the first fix | Delta |
| --- | --- | --- | --- |
| navbar container | x=148 | x=148 | 0 |
| navbar brand/logo | x=164 | x=164 | 0 |
| page-head toggle | x=163 | x=15 | **−148** |
| sidebar | x=148 | x=0 | **−148** |
| sidebar first item | x=153 | x=5 | **−148** |
| main section | x=378 | x=279 | **−99** |

Stock Frappe aligns the navbar brand (164), page head (163) and sidebar (153)
within ~11px. The first fix widened `.page-head > .container` and
`.container.page-body` but not `header.navbar .container`, which lives outside
`.page-container` entirely. That pulled everything except the navbar to x=0 and
left a **148px** disagreement between the navbar and everything below it.

## Root causes in `tradexcel_desk.css`

1. `.page-container { padding-left/right: 24px }` — Frappe's `.page-container`
   has no padding of its own, and a desk page *is* `.content.page-container`
   containing both `.page-head` and the sidebar. The padding shifted the entire
   page, sidebar included.
2. `.page-container > .container` — a direct-child selector. It reaches
   `.container.page-body` but not `.page-head > .container`, and never the navbar
   container. Widening an incomplete set of containers is what produces the
   different left edges.

## Fix

Widen every container together — `.page-container`, `header.navbar .container`,
`.page-head > .container`, `.page-body.container`, `.layout-main-section-wrapper`,
`.layout-main-section`, `.workspace-page`, `.workspace-container` — and add no
padding, leaving the inset to Bootstrap's own container padding.

## Verified end state

| Element | x |
| --- | --- |
| navbar container | 0 (padding-left 16px) |
| page-head toggle | 15 |
| sidebar first item | 5 |
| `img.app-logo` | hidden (0x0) |

No horizontal overflow (`scrollWidth == innerWidth`). Sidebar-to-head spacing
retains Frappe's native 10px relationship.

## Navbar app logo

The ERPNext "e" was not a bug in our code. `get_app_logo()` resolves in order:

```
Website Settings.app_logo  →  Navbar Settings.app_logo  →  frappe.get_hooks("app_logo_url")
```

Neither setting is populated, so it fell through to
`erpnext/hooks.py: app_logo_url = "/assets/erpnext/images/erpnext-logo.svg"`.
`header.navbar .navbar-brand` is hidden in CSS. **To show a Tradexcel logo
instead of hiding it, set Desk > Website > Website Settings > App Logo** — that
setting takes priority and needs no code change.

Note: `tabNavbar Settings` does not exist on this site, so the Navbar Settings
fallback is inert and the hook is what renders.
