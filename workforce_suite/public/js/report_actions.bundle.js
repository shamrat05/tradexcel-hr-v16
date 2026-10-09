// Own only this app's actions. QueryReport reuses one Page across report routes;
// v16 clears the inner toolbar, but not its responsive menu copies or primary.
frappe.provide("workforce_suite.report_actions");
(() => {
    let current;
    const route_matches = (name) => {
        const route = frappe.get_route();
        return route[0] === "query-report" && route[1] === name;
    };
    frappe.router.on("change", () => {
        // Returning from a Form/List to the same report does not rerun onload
        // in native v16. Keep that hidden Page's actions, but guard callbacks.
        const route = frappe.get_route();
        if (current && route[0] === "query-report" && route[1] !== current.name) current.clear();
    });
    workforce_suite.report_actions.begin = (report) => {
        if (current) current.clear();
        const page = report.page;
        const buttons = [];
        const menu_items = [];
        let primary;
        const actions = {
            name: report.report_name,
            is_current: () => current === actions && route_matches(actions.name),
            add(label, callback, group) {
                const before = new Set(page.menu.children().toArray());
                const button = page.add_inner_button(label, () => {
                    if (actions.is_current()) return callback();
                }, group);
                // Capture only nodes created by this native call. Never clear
                // native Print/Export, other apps' actions, or the whole menu.
                page.menu.children().each((_, node) => {
                    if (!before.has(node)) menu_items.push(node);
                });
                buttons.push([label, group]);
                return button;
            },
            primary(label, callback) {
                const button = page.set_primary_action(label, () => {
                    if (actions.is_current()) return callback();
                });
                // Native shortcut registration encodes data-label. Remember
                // the actual native value rather than assuming plain text.
                primary = page.btn_primary.attr("data-label");
                return button;
            },
            clear() {
                for (const [label, group] of buttons) page.remove_inner_button(label, group);
                for (const node of menu_items) node.remove();
                if (primary && page.btn_primary.attr("data-label") === primary) page.clear_primary_action();
                if (current === actions) current = null;
            },
        };
        current = actions;
        report.workforce_actions = actions;
        return actions;
    };
})();
