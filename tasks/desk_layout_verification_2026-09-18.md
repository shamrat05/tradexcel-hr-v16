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
with chromium at `~/.cache/ms-playwright`.

**The desk CSS is now a built bundle, so `bench build` IS required after every
edit** — see "Asset caching" below for why. On a fresh Playwright context the
browser cache is empty, so fine-grained CSS checks are reliable there in a way
they are not in a long-lived Chrome profile.

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

## Asset caching — why the desk looked stale for hours

`/assets` is served by werkzeug's `SharedDataMiddleware` (`frappe/app.py`):

```python
SharedDataMiddleware(application, {"/assets": ...})   # default cache_timeout=43200
```

That emits `Cache-Control: max-age=43200, public` — **12 hours with no
revalidation**. Frappe only escapes this for *built bundles*, because
`bundled_asset()` skips versioning for raw paths:

```python
def bundled_asset(path, rtl=None):
	if ".bundle." in path and not path.startswith("/assets"):   # raw paths fail this
		path = bundled_assets.get(path) or path
	return abs_url(path)
```

The original `app_include_css = ["/assets/tradex_hr/css/tradexcel_desk.css"]`
started with `/assets` and had no hash, so the browser legitimately reused a
stale copy for 12 hours. No amount of reloading from the app could help.

### Fix: serve it as a content-hashed bundle

Frappe discovers bundles by filename — source files must literally be named
`*.bundle.css` / `*.bundle.js` (compare `frappe/public/js/desk.bundle.js`). A
`build.json` is not required for this; `get_all_files_to_build()` globs
`**/*.bundle.{js,css}`.

```bash
git mv tradex_hr/public/css/tradexcel_desk.css \
       tradex_hr/public/css/tradex_hr.bundle.css
# hooks.py
app_include_css = ["tradex_hr.bundle.css"]
bench build --app tradex_hr
```

Result:

```
sites/assets/assets.json
  "tradex_hr.bundle.css": "/assets/tradex_hr/dist/css/tradex_hr.bundle.2P673ZWD.css"
```

The filename now carries a content hash, so **the URL changes whenever the CSS
changes** and a stale cache cannot be served. The 12-hour `max-age` is harmless
once the name is content-addressed.

### Working on the CSS

```bash
# edit tradex_hr/public/css/tradex_hr.bundle.css, then:
cd ~/frappe-bench && bench build --app tradex_hr
```

The hash changes, so even a long-lived Chrome profile picks it up on a normal
reload — no cache clearing. `bench watch` rebuilds automatically if you want it.

### Same exposure on the JS files

`doctype_js` / `doctype_list_js` entries still reference raw paths
(`public/js/list_scope.js`, `public/js/employee_calendar.js`), so they carry the
same 12-hour cache and will appear stale after an edit until rebuilt as bundles
or cache-cleared. Not changed here; recorded as a known gap.

## Proportions on wide screens

Going full bleed changed proportions, not just width, because two things are
percentage-based. Measured stock vs full-bleed at 1600px:

| Metric | Stock | Full bleed | Effect |
| --- | --- | --- | --- |
| navbar container | 1290 | 1585 | — |
| nav inset from right edge | 178px | **31px** | Help/avatar appear hard against the screen edge |
| `.layout-side-section` | 215px (13.4%) | **264px (16.5%)** | the expanded left menu inflates, and keeps growing with the screen |
| main wrapper | 1075 | 1321 | gains the space instead |

`.layout-side-section` is `col-lg-2` — a percentage of the container — so
widening the container inflates the sidebar with it.

**Fix:** pin `.layout-side-section { max-width: 215px }` to Frappe's stock
proportion (the adjacent `col` absorbs the reclaimed width), and give
`header.navbar .container` 24px horizontal padding so the search bar, Help menu
and avatar are not flush against the edge.

Compared with stock after the fix:

| Metric | Stock | Ours |
| --- | --- | --- |
| sidebar | y=113, h=787, w=215 | y=113, h=787, w=215 |
| page head | y=48, h=60 | y=48, h=60 |
| main section | y=113 | y=113 |
| first sidebar item | y=146, gap 30 | y=146, gap 30 |
| nav inset from right | 178 | 39 |

Vertical geometry is identical to stock — the widening changed horizontal
proportions only. Note below ~1280px our CSS is byte-identical to stock, because
Frappe's container is already full width there; these effects appear only on
wide screens.

### If the layout looks stale

The bundle filename carries a content hash, so a CSS change produces a new URL
and is picked up on a normal reload. Check which file the page requests:

```bash
curl -s http://localhost:8000/app | grep -o 'tradex_hr.bundle[^"]*css'
```
