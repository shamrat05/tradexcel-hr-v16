# Desk navbar theme toggle — 2026-09-18

A one-click light/dark button in the Desk navbar, plus the two Frappe-specific
traps that broke the first two attempts.

## Why DOM injection and not a hook

Frappe does document navbar customisation hooks:

```python
# app hooks.py — appends to the HELP and SETTINGS dropdowns
standard_help_items = [
	{"item_label": "About", "item_type": "Action",
	 "action": "frappe.ui.toolbar.show_about()", "is_standard": 1},
]
standard_navbar_items = [...]   # same shape, settings dropdown
```

Those only populate the **dropdowns** (`#toolbar-help`, `#toolbar-user`). There
is no hook for a stand-alone top-level navbar button, so the button is injected
from `app_include_js` via the one documented extension point:

```js
// frappe/public/js/frappe/ui/toolbar/toolbar.js
make() {
	this.bind_events();
	$(document).trigger("toolbar_setup");   // the hook
}
```

Shipped as `workforce_suite/public/js/workforce_suite.bundle.js`, referenced by bundle name
so the filename is content-hashed (see the asset-caching section of
`desk_layout_verification_2026-09-18.md`).

## Trap 1 — `header .navbar` matches nothing

The `<header>` element **itself** carries the `navbar` class:

```html
<header class="navbar navbar-expand">
```

so `header .navbar` (descendant) matches nothing; it must be `header.navbar`.

## Trap 2 — there are TWO `ul.navbar-nav`, and breadcrumbs are one

```
ul.navbar-nav  (id=navbar-breadcrumbs)   <-- index 0
ul.navbar-nav  (inside .navbar-collapse) <-- the real one, holds #toolbar-help / #toolbar-user
```

`$("header.navbar ul.navbar-nav").first()` picks the **breadcrumbs** list. Frappe
re-renders breadcrumbs on every route change, so a button inserted there is wiped
immediately — `render()` returned `true` and the button was still gone one second
later. Symptom: works on first paint, never survives navigation.

Anchor on the element that is actually in the menu list:

```js
const $nav = $("#toolbar-user").closest("ul.navbar-nav");
```

## Trap 3 — `toolbar_setup` fires once, and ordering is not guaranteed

Measured: after an in-desk navigation, `toolbar_setup` handlers run **0** times
while `page-change` runs. And `app_include_js` and the `Toolbar` constructor both
run during boot with no guaranteed order, so a one-shot `toolbar_setup` listener
can miss the event entirely.

So the module renders on `toolbar_setup`, on `page-change`, and on a short
bounded poll (40 x 250ms) until the navbar exists.

## Theme implementation

Frappe's own switcher is a dialog:

```js
// the stock "Toggle Theme" navbar item
new frappe.ui.ThemeSwitcher().show()
```

The button instead flips directly and persists against the user:

```js
document.documentElement.setAttribute("data-theme-mode", next);
frappe.ui.set_theme(next);
frappe.xcall("frappe.core.doctype.user.user.switch_theme", { theme: label });
```

## Verified (single serial browser session)

| Check | Result |
| --- | --- |
| at load | button present in the user menu list, not breadcrumbs |
| SPA nav → Employee / Attendance / workspace | survives each |
| full page load → `/app/employee`, `/app/workforce-suite` | survives each |
| click | `dark → light`, tooltip flips to "Switch to Dark theme" |
| theme restored, session logged out afterwards | yes |

## Note on the stock alternative

If the injected button is ever undesirable, the *supported* alternative costs no
JavaScript: change the existing `Toggle Theme` Navbar Item's `action` from
`new frappe.ui.ThemeSwitcher().show()` to a direct toggle expression. It stays
inside the user dropdown rather than being a visible button.
