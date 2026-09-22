// Tradexcel HR desk additions.
//
// Loaded via `app_include_js = ["tradex_hr.bundle.js"]`, so Frappe serves it
// from a content-hashed filename (assets.json) and browser caching cannot leave
// a stale copy behind — see tasks/desk_layout_verification_2026-09-18.md.
//
// Includes the theme toggle and a persistent, data-driven HR navigation rail.
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

(function () {
	// Frappe v16 treats add_to_apps_screen links as External and opens them in
	// a new tab. Keep this app tile inside the current Desk session without
	// changing Frappe core or affecting other external links.
	function keepTradexcelTileInDesk(attempt) {
		const tile = Array.from(document.querySelectorAll(".desktop-icon")).find(
			(element) => element.getAttribute("data-id") === "Tradexcel HR"
		);
		if (!tile) {
			if ((attempt || 0) < 20) window.setTimeout(() => keepTradexcelTileInDesk((attempt || 0) + 1), 250);
			return;
		}
		tile.removeAttribute("target");
		tile.setAttribute("href", "/desk/tradexcel-hr");
	}

	$(function () {
		keepTradexcelTileInDesk(0);
	});
	$(document).on("page-change", function () {
		if ((frappe.get_route_str && frappe.get_route_str()) === "apps") keepTradexcelTileInDesk(0);
	});
})();

(function () {
	const STORAGE_KEY = "tradexcel_hr_sidebar_collapsed";
	const RAIL_CLASS = "tradex-hr-rail";
	const GROUP_CLASS = "tradex-hr-rail-group";

	// Keep routes in one registry so the same navigation works on workspaces,
	// lists, reports, forms and payroll screens. Labels are user-facing; routes
	// are native Frappe routes or records installed by tradex_hr.
	const GROUPS = [
		{
			label: __("Home"),
			icon: "home",
			items: [
				{ label: __("Command Center"), route: "tradexcel-hr", primary: true },
				{ label: __("My Tasks"), route: "List/ToDo" },
				{ label: __("Notifications"), route: "List/Notification Log" },
			],
		},
		{
			label: __("People"),
			icon: "people",
			items: [
				{ label: __("Employees"), route: "List/Employee", primary: true },
				{ label: __("Directory"), route: "List/Employee" },
				{ label: __("Departments"), route: "List/Department" },
				{ label: __("Designations"), route: "List/Designation" },
				{ label: __("Transfers"), route: "List/Employee Transfer" },
				{ label: __("Onboarding"), route: "List/Employee Onboarding" },
				{ label: __("Separations"), route: "List/Employee Separation" },
				{ label: __("Final Settlement"), route: "List/Full and Final Statement" },
			],
		},
		{
			label: __("Time & Attendance"),
			icon: "clock",
			items: [
				{ label: __("Today"), route: "query-report/Tradexcel Daily Attendance Board", primary: true },
				{ label: __("Attendance"), route: "List/Attendance" },
				{ label: __("Punches"), route: "List/Employee Checkin" },
				{ label: __("Attendance Requests"), route: "List/Attendance Request" },
				{ label: __("Shifts"), route: "List/Shift Type" },
				{ label: __("Shift Planner"), route: "List/Shift Schedule" },
				{ label: __("Shift Assignments"), route: "List/Shift Assignment" },
			],
		},
		{
			label: __("Leave"),
			icon: "leave",
			items: [
				{ label: __("Leave Requests"), route: "List/Leave Application", primary: true },
				{ label: __("Leave Calendar"), route: "leave-application/view/calendar" },
				{ label: __("Allocations"), route: "List/Leave Allocation" },
				{ label: __("Balances"), route: "query-report/Tradexcel Leave Balance Board" },
				{ label: __("Leave Policies"), route: "List/Leave Policy" },
			],
		},
		{
			label: __("Payroll"),
			icon: "money",
			items: [
				{ label: __("Payroll Run"), route: "List/Payroll Entry", primary: true },
				{ label: __("Salary Slips"), route: "List/Salary Slip" },
				{ label: __("Assignments"), route: "List/Salary Structure Assignment" },
				{ label: __("Structures"), route: "List/Salary Structure" },
				{ label: __("Components"), route: "List/Salary Component" },
				{ label: __("Additional Salary"), route: "List/Additional Salary" },
				{ label: __("Payroll Rules"), route: "List/Tradexcel Payroll Policy" },
			],
		},
		{
			label: __("Operations"),
			icon: "check",
			items: [
				{ label: __("Action Queue"), route: "query-report/Workforce Anomaly Radar", primary: true },
				{ label: __("Missing Data"), route: "query-report/Employee Data Gaps" },
				{ label: __("Exceptions"), route: "List/Tradexcel Policy Exception" },
				{ label: __("Anomalies"), route: "query-report/Workforce Anomaly Radar" },
			],
		},
		{
			label: __("Devices"),
			icon: "device",
			items: [
				{ label: __("Biometric Devices"), route: "List/Tradexcel Biometric Device", primary: true },
				{ label: __("Employee PINs"), route: "List/Tradexcel Employee Biometric" },
				{ label: __("Device Health"), route: "query-report/Biometric ID Audit" },
				{ label: __("Sync Problems"), route: "List/Tradex Mobile Event" },
				{ label: __("Live Locations"), route: "List/Tradexcel Location Ping" },
			],
		},
		{
			label: __("Analytics"),
			icon: "chart",
			items: [
				{ label: __("HR Overview"), route: "tradexcel-hr", primary: true },
				{ label: __("Attendance"), route: "query-report/Daily Attendance Summary" },
				{ label: __("Payroll"), route: "query-report/Tradexcel Payroll Register" },
				{ label: __("Workforce"), route: "query-report/Tradexcel Salary Coverage Board" },
				{ label: __("Leave"), route: "query-report/Tradexcel Leave Balance Board" },
			],
		},
		{
			label: __("Administration"),
			icon: "settings",
			items: [
				{ label: __("HR Setup"), route: "tradexcel-hr", primary: true },
				{ label: __("Roles"), route: "List/Role" },
				{ label: __("Imports"), route: "List/Data Import" },
				{ label: __("Workflows"), route: "List/Workflow" },
				{ label: __("Policies"), route: "List/Tradexcel Attendance Policy" },
			],
		},
	];

	const ICONS = {
		home: "M3 10.5 12 3l9 7.5M5 9v11h14V9M9 20v-6h6v6",
		people: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm7-7a4 4 0 0 1 0 7.75M22 21v-2a4 4 0 0 0-3-3.87",
		clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-14v5l3 2",
		leave: "M12 21s-7-4.35-7-10a4 4 0 0 1 7-2.65A4 4 0 0 1 19 11c0 5.65-7 10-7 10Z",
		money: "M3 6h18v12H3zM7 10h.01M17 14h.01M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z",
		check: "M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
		device: "M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm4 4h6v4H9zM7 15h.01M11 15h.01M15 15h.01M7 18h.01M11 18h.01M15 18h.01",
		chart: "M4 19V5M4 19h17M8 16v-5M12 16V7M16 16v-3M20 16V9",
		settings: "M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm8.5-3.5a6.5 6.5 0 0 0-.1-1.1l2-1.55-2-3.46-2.35.95a7 7 0 0 0-1.9-1.1L15.8 3h-4l-.35 2.75a7 7 0 0 0-1.9 1.1L7.2 5.9l-2 3.46 2 1.55a6.5 6.5 0 0 0 0 2.2l-2 1.55 2 3.46 2.35-.95a7 7 0 0 0 1.9 1.1L11.8 21h4l.35-2.75a7 7 0 0 0 1.9-1.1l2.35.95 2-3.46-2-1.55c.06-.36.1-.73.1-1.1Z",
	};

	function icon(name, className) {
		return `<svg class="${className || ""}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${ICONS[name] || ICONS.home}"/></svg>`;
	}

	function collapsed() {
		try {
			return window.localStorage.getItem(STORAGE_KEY) === "1";
		} catch (error) {
			return false;
		}
	}

	function saveCollapsed(value) {
		try {
			window.localStorage.setItem(STORAGE_KEY, value ? "1" : "0");
		} catch (error) {
			// Private browsing can disable localStorage; the current page still works.
		}
	}

	function active(route) {
		let current = "";
		try {
			current = (frappe.get_route_str && frappe.get_route_str()) || "";
		} catch (error) {
			// During Desk boot Frappe can expose get_route_str before its route
			// array exists. The rail can render with no active item and refresh
			// it on the next page-change event.
			return false;
		}
		const currentRoute = current.split("?")[0].toLowerCase();
		const itemRoute = route.split("?")[0].toLowerCase();

		// A Desk workspace reports as "Workspaces/<slug>" in the route string, not
		// as the workspace title, so match on the slug. Matching the title ("tradexcel hr")
		// could never be true, so the workspace items never highlighted.
		const workspaceName =
			itemRoute.indexOf("workspace/") === 0 ? itemRoute.slice("workspace/".length) : itemRoute;
		if (workspaceName === "tradexcel-hr") {
			return currentRoute === `workspaces/${workspaceName}` || currentRoute === workspaceName;
		}

		// List routes carry the view type ("List/Employee/List"), so the previous exact
		// equality could never match and no list item ever highlighted. Compare the first
		// two segments only -- a prefix test would wrongly light "List/Employee" while on
		// "List/Employee Checkin".
		const [currentType, currentName] = currentRoute.split("/");
		const [itemType, itemName] = itemRoute.split("/");
		return Boolean(currentType) && currentType === itemType && currentName === itemName;
	}

	function navigate(route) {
		const destination = resolvedRoute(route);
		// Frappe treats the route as path segments. Query-string text passed to
		// set_route() is encoded into the report name, so use the native
		// route_options hand-off for initial report filters.
		frappe.route_options = Object.keys(destination.options).length
			? destination.options
			: null;
		frappe.set_route(destination.route);
	}

	function resolvedRoute(route) {
		const today = frappe.datetime && frappe.datetime.get_today
			? frappe.datetime.get_today()
			: "";
		const company =
			(frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) ||
			"";
		const options = {};
		if (route === "query-report/Tradexcel Daily Attendance Board") {
			options.attendance_date = today;
			if (company) options.company = company;
		} else if (route === "query-report/Tradexcel Leave Balance Board") {
			options.as_of_date = today;
			if (company) options.company = company;
		} else if (route === "query-report/Tradexcel Payroll Register") {
			options.from_date = (frappe.datetime.month_start && frappe.datetime.month_start()) || today;
			options.to_date = today;
			if (company) options.company = company;
		}
		return { route, options };
	}

	function render() {
		if (!document.body) return;
		const existing = document.querySelector(`.${RAIL_CLASS}`);
		if (existing && existing.querySelector(`.${GROUP_CLASS}`)) return;
		// Frappe replaces page shells during route changes. Keep the shell only
		// when it is complete; rebuild an emptied rail instead of showing a blank
		// 248px reservation on list/report/form pages.
		if (existing) existing.remove();
		document.body.classList.add("tradex-hr-rail-enabled");
		const aside = document.createElement("aside");
		aside.className = RAIL_CLASS;
		aside.setAttribute("aria-label", __("Tradexcel HR navigation"));
		aside.innerHTML = `
			<div class="tradex-hr-rail-header">
				<a class="tradex-hr-rail-brand" href="#" aria-label="${__("Command Center")}">
					<span class="tradex-hr-rail-brand-mark">T</span><span class="tradex-hr-rail-brand-text">Tradexcel HR</span>
				</a>
				<button class="tradex-hr-rail-toggle" type="button" aria-label="${__("Collapse navigation")}" aria-expanded="true">${icon("chevron", "")}</button>
			</div>
			<nav class="tradex-hr-rail-nav"></nav>`;
		document.body.appendChild(aside);
		const nav = aside.querySelector(".tradex-hr-rail-nav");
		GROUPS.forEach((group, groupIndex) => {
			const section = document.createElement("section");
			section.className = GROUP_CLASS;
			const heading = document.createElement("button");
			heading.className = "tradex-hr-rail-group-heading";
			heading.type = "button";
			heading.innerHTML = `${icon(group.icon, "tradex-hr-rail-icon")}<span>${group.label}</span><span class="tradex-hr-rail-chevron">⌄</span>`;
			heading.setAttribute("aria-expanded", groupIndex === 0 ? "true" : "true");
			const list = document.createElement("div");
			list.className = "tradex-hr-rail-items";
			group.items.forEach((item) => {
				const link = document.createElement("a");
				link.className = `tradex-hr-rail-item${item.primary ? " is-primary" : ""}${active(item.route) ? " is-active" : ""}`;
				link.href = `#${item.route}`;
				link.title = item.label;
				link.dataset.route = item.route;
				link.innerHTML = `${icon(group.icon, "tradex-hr-rail-item-icon")}<span>${item.label}</span>`;
				link.addEventListener("click", (event) => {
					event.preventDefault();
					navigate(item.route);
				});
				list.appendChild(link);
			});
			heading.addEventListener("click", () => {
				const open = heading.getAttribute("aria-expanded") === "true";
				heading.setAttribute("aria-expanded", String(!open));
				list.hidden = open;
			});
			section.append(heading, list);
			nav.appendChild(section);
		});

		const toggle = aside.querySelector(".tradex-hr-rail-toggle");
		const applyCollapsed = (value) => {
			document.body.classList.toggle("tradex-hr-rail-collapsed", value);
			toggle.setAttribute("aria-expanded", String(!value));
			toggle.setAttribute("aria-label", value ? __("Expand navigation") : __("Collapse navigation"));
			toggle.innerHTML = value ? "›" : "‹";
			saveCollapsed(value);
		};
		toggle.addEventListener("click", () => applyCollapsed(!document.body.classList.contains("tradex-hr-rail-collapsed")));
		aside.querySelector(".tradex-hr-rail-brand").addEventListener("click", (event) => {
			event.preventDefault();
			navigate("tradexcel-hr");
		});
		applyCollapsed(collapsed());
	}

	function refreshActive() {
		const rail = document.querySelector(`.${RAIL_CLASS}`);
		if (!rail) return;
		// Key each link off its own route. Matching by label broke as soon as two
		// items shared one: "Attendance" exists in Time & Attendance (List/Attendance)
		// and in Analytics (query-report/Daily Attendance Summary), so the later item
		// toggled the class on the earlier item's link and cleared it again.
		rail.querySelectorAll(".tradex-hr-rail-item").forEach((link) => {
			const route = link.dataset.route;
			link.classList.toggle("is-active", Boolean(route) && active(route));
		});
	}

	function ensureRail() {
		render();
		if (!document.querySelector(`.${RAIL_CLASS} .${GROUP_CLASS}`)) {
			window.setTimeout(render, 0);
			window.setTimeout(render, 250);
		}
	}

	$(function () {
		ensureRail();
		$(document).on("page-change", function () {
			ensureRail();
			refreshActive();
		});
	});
})();
