// Tradexcel HR desk additions.
//
// Loaded via `app_include_js = ["tradex_hr.bundle.js"]`, so Frappe serves it
// from a content-hashed filename (assets.json) and browser caching cannot leave
// a stale copy behind — see tasks/desk_layout_verification_2026-09-18.md.
//
// Currently: a one-click light/dark theme toggle in the navbar.
//
// The desk navbar exposes one supported extension point: Toolbar.make() fires
// `toolbar_setup` on document, and Frappe injects its own items the same way.
// Frappe clears `.custom-menu` items on `page-change`, so the button is
// re-rendered on that event too rather than being added once at boot.

frappe.provide("frappe.ui.tradex_hr");

(function () {
	const SEL = ".tradex-theme-toggle";
	const MOON =
		'<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
	const SUN =
		'<circle cx="12" cy="12" r="4"/>' +
		'<path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41' +
		'M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>';

	frappe.ui.tradex_hr.current_theme = function () {
		return document.documentElement.getAttribute("data-theme-mode") || "light";
	};

	frappe.ui.tradex_hr.toggle_theme = function () {
		const next = frappe.ui.tradex_hr.current_theme() === "dark" ? "light" : "dark";

		// apply immediately, then persist against the user
		document.documentElement.setAttribute("data-theme-mode", next);
		frappe.ui.set_theme(next);
		frappe.ui.tradex_hr.render();

		const label = next.charAt(0).toUpperCase() + next.slice(1);
		frappe.xcall("frappe.core.doctype.user.user.switch_theme", { theme: label });
	};

	frappe.ui.tradex_hr.render = function () {
		// There are TWO `ul.navbar-nav` elements: `#navbar-breadcrumbs` also
		// carries that class, and Frappe re-renders breadcrumbs on every route
		// change — injecting there makes the button vanish immediately. Anchor
		// on the user dropdown instead, which lives in the list that actually
		// holds the notifications / help / user menus.
		const $nav = $("#toolbar-user").closest("ul.navbar-nav");
		if (!$nav.length) return false;

		$nav.find(SEL).remove();

		const going_to = frappe.ui.tradex_hr.current_theme() === "dark" ? "light" : "dark";
		const $li = $(`
			<li class="nav-item ${SEL.slice(1)}">
				<button class="btn-reset nav-link" type="button"
					title="${__("Switch to {0} theme", [__(going_to === "dark" ? "Dark" : "Light")])}"
					aria-label="${__("Toggle Theme")}">
					<svg class="es-icon icon-sm" viewBox="0 0 24 24" fill="none"
						stroke="currentColor" stroke-width="1.5"
						stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						${going_to === "dark" ? MOON : SUN}
					</svg>
				</button>
			</li>`);

		$li.find("button").on("click", frappe.ui.tradex_hr.toggle_theme);
		$nav.prepend($li);
		return true;
	};

	// Rendering once is not enough. `app_include_js` and the Toolbar
	// constructor both run during desk boot and their relative order is not
	// guaranteed, so `toolbar_setup` may already have fired before this file
	// executed — in which case a one-shot listener never runs. Poll briefly
	// until the navbar exists, and re-arm on every `page-change`.
	frappe.ui.tradex_hr.ensure = function (attempt) {
		attempt = attempt || 0;
		if (frappe.ui.tradex_hr.render()) return;
		if (attempt < 40) {
			setTimeout(function () {
				frappe.ui.tradex_hr.ensure(attempt + 1);
			}, 250);
		}
	};

	$(function () {
		frappe.ui.tradex_hr.ensure();
	});
	$(document).on("toolbar_setup page-change", function () {
		frappe.ui.tradex_hr.ensure();
	});
})();
