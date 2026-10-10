// Link/date conveniences only. Native server permissions remain the access boundary.
const WORKFORCE_SCOPED_LIST_DOCTYPES = [
	"Employee",
	"Attendance",
	"Employee Checkin",
	"Salary Slip",
	"Leave Application",
	"Salary Structure Assignment",
	"Leave Allocation",
	"Additional Salary",
	"Payroll Entry",
];

// doctype -> its primary date/datetime field for quick range filters
const WORKFORCE_LIST_DATE_FIELDS = {
	"Attendance": "attendance_date",
	"Employee Checkin": "time",
	"Salary Slip": "start_date",
	"Leave Application": "from_date",
	"Salary Structure Assignment": "from_date",
	"Leave Allocation": "from_date",
	"Additional Salary": "payroll_date",
	"Payroll Entry": "posting_date",
};

// Attendance already has a separate date column; Checkin must retain its date.
const WORKFORCE_LIST_TIME_FIELDS = {
	"Attendance": ["in_time", "out_time"],
};

function build_time_formatters(doctype) {
	const formatters = {};
	(WORKFORCE_LIST_TIME_FIELDS[doctype] || []).forEach((field) => {
		formatters[field] = (value) => (value ? moment(value).format("hh:mm A") : "");
	});
	if (doctype === "Employee Checkin") {
		formatters.time = (value) => value ? frappe.datetime.str_to_user(value) : "";
	}
	return formatters;
}

function apply_scoped_list_filters(listview) {
	const fields = listview.page.fields_dict || {};
	const filters = listview.filter_area.get() || [];
	const value = (field) => {
		const row = filters.find((r) => r[1] === field && r[2] === "=");
		return row ? row[3] : null;
	};
	const company = fields.company ? value("company") : null;
	const branch = fields.branch ? value("branch") : null;
	const department = fields.department ? value("department") : null;
	const designation = fields.designation ? value("designation") : null;

	if (fields.branch) {
		fields.branch.get_query = () => (company ? { filters: { company } } : {});
	}
	if (fields.department) {
		fields.department.get_query = () => {
			if (branch && company) {
				return {
					query: "workforce_suite.link_filters.departments_used_by_branch",
					filters: { company, branch },
				};
			}
			return company ? { filters: { company } } : {};
		};
	}
	if (fields.designation) {
		fields.designation.get_query = () => {
			const scoped = {};
			if (company) scoped.company = company;
			if (branch) scoped.branch = branch;
			if (department) scoped.department = department;
			if (!branch && !department) {
				return company ? { filters: { company } } : {};
			}
			return {
				query: "workforce_suite.link_filters.designations_used_by_scope",
				filters: scoped,
			};
		};
	}
	if (fields.employee) {
		fields.employee.get_query = () => {
			const scoped = {};
			if (company) scoped.company = company;
			if (branch) scoped.branch = branch;
			if (department) scoped.department = department;
			if (designation) scoped.designation = designation;
			return Object.keys(scoped).length ? { filters: scoped } : {};
		};
	}
}

function apply_date_filter(listview, doctype, date_field, operator, value) {
	if (!date_field) return;
	const keep = (listview.filter_area.get() || []).filter((row) => row[1] !== date_field);
	listview.filter_area.clear(false);
	listview.filter_area.add(keep.concat([[doctype, date_field, operator, value, false]]));
	apply_scoped_list_filters(listview);
}

function add_quick_date_filters(listview, doctype) {
	const date_field = WORKFORCE_LIST_DATE_FIELDS[doctype];
	if (!date_field || !frappe.meta.has_field(doctype, date_field)) return;
	// Native Page groups supply a compact desktop menu and mobile Actions entry.
	// Advanced ranges and saved filters remain Frappe's own Filter UI.
	const add = (label, action) => listview.page.add_inner_button(label, action, __("Date"));
	add(__("Today"), () => apply_date_filter(listview, doctype, date_field, "Timespan", "today"));
	add(__("This Week"), () => apply_date_filter(listview, doctype, date_field, "Timespan", "this week"));
	add(__("This Month"), () => apply_date_filter(listview, doctype, date_field, "Timespan", "this month"));
}

WORKFORCE_SCOPED_LIST_DOCTYPES.forEach((doctype) => {
	const existing = frappe.listview_settings[doctype] || {};
	const previous_onload = existing.onload;
	const previous_refresh = existing.refresh;
	frappe.listview_settings[doctype] = Object.assign(existing, {
		formatters: Object.assign(
			build_time_formatters(doctype),
			existing.formatters || {}
		),
		onload(listview) {
			if (typeof previous_onload === "function") previous_onload(listview);
			apply_scoped_list_filters(listview);
			const wrapper = listview.filter_area && listview.filter_area.standard_filters_wrapper;
			if (wrapper) {
				wrapper
					.off("change.workforce_scope")
					.on("change.workforce_scope", "input, select", () => {
						setTimeout(() => apply_scoped_list_filters(listview), 0);
					});
			}
		},
		refresh(listview) {
			if (typeof previous_refresh === "function") previous_refresh(listview);
			apply_scoped_list_filters(listview);
			if (!listview.__workforce_quick_filters) {
				listview.__workforce_quick_filters = true;
				add_quick_date_filters(listview, doctype);
			}
		},
	});
});
