// Native Workspace Custom HTML Block: Frappe supplies root_element.
(() => {
  const root = root_element.querySelector(".action-board");
  const filters = root.querySelector(".filters");
  const notice = root.querySelector(".notice");
  const items = root.querySelector(".items");
  const method = "tradex_hr.tradexcel_hr.action_board.";
  let generation = 0;
  function element(tag, text, parent) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (parent) parent.append(node);
    return node;
  }
  function field(label, tag) {
    const wrapper = element("label", __(label), filters);
    return element(tag, undefined, wrapper);
  }
  const company = field("Company", "select");
  const date = field("Review date", "input");
  date.type = "date";
  const refresh = element("button", __("Review work"), filters);
  refresh.type = "button";
  async function load() {
    const request = ++generation;
    items.replaceChildren();
    if (!company.value) {
      notice.textContent = __("Choose a Company to review your work.");
      return;
    }
    refresh.disabled = true;
    notice.textContent = __("Loading work needing attention…");
    try {
      const response = await frappe.call({method: method + "get_action_board", args: {company: company.value, as_of_date: date.value}});
      if (request !== generation || !root.isConnected) return;
      const data = response.message;
      notice.textContent = data.notice;
      for (const item of data.items) {
        const card = element("article", undefined, items);
        card.className = "item";
        element("span", __(item.category), card).className = "category";
        element("h3", item.title + (item.count === null ? "" : " (" + item.count + ")"), card);
        element("p", item.reason, card);
        if (!item.route.length) continue;
        const open = element("button", __("Open review"), card);
        open.type = "button";
        open.addEventListener("click", () => {
          frappe.route_options = item.filters || {};
          frappe.set_route(...item.route);
        });
      }
      if (!data.items.length) element("p", __("No outstanding items were found in the available reviews for your scope."), items);
    } catch (_error) {
      if (request === generation) notice.textContent = __("This review could not be loaded. Check your access and try again.");
    } finally {
      if (request === generation) refresh.disabled = false;
    }
  }
  refresh.addEventListener("click", load);
  company.addEventListener("change", load);
  frappe.call({method: method + "get_board_context"}).then(response => {
    const data = response.message;
    element("option", __("Choose Company"), company).value = "";
    for (const name of data.companies) element("option", name, company).value = name;
    company.value = data.company;
    date.value = data.as_of_date;
    load();
  }).catch(() => {
    filters.hidden = true;
    notice.textContent = __("Your role does not use this management work board.");
  });
})();
