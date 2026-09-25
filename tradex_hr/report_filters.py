"""Server-side filter normalisation for DB-backed Query Reports.

Why this exists
---------------
A Frappe **Query Report** interpolates its SQL with the filter dict directly:

    frappe.db.sql(self.query, filters)          # frappe/core/doctype/report/report.py

so any placeholder the caller did not supply raises **from the database driver**
— `KeyError: b'from_date'` or `ProgrammingError: format requires a mapping` —
*before MariaDB ever sees the query*. The user sees a Python traceback rather
than a report or a usable message.

Operational reports are promoted to standard Script Reports and normalise their
own filters in Python. The remaining salary-sensitive DB-backed Query Reports
cannot run Python, so this wrapper supplies the missing values at the one place
all callers pass through.

It is wired via `override_whitelisted_methods` in hooks.py, which is Frappe's
supported extension point — no core files are modified.

Scope is deliberately narrow: only the app's own report names, and only
placeholders whose default is unambiguous (dates and the user's Company). An
unknown placeholder is left untouched so the report still fails loudly rather
than silently querying the wrong thing.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

import frappe
from frappe.utils import today

_PLACEHOLDER = re.compile(r"%\((\w+)\)s")


def placeholder_defaults(query: str) -> dict:
    """Safe defaults for the unambiguous placeholders in `query`.

    Returns only values we can fill with confidence; anything else is omitted so
    the report fails visibly instead of being fed an invented figure.
    """
    out = {}
    for field in _PLACEHOLDER.findall(query or ""):
        lowered = field.lower()
        if lowered in ("from_date", "start_date"):
            out[field] = frappe.utils.get_first_day(today())
        elif lowered in ("to_date", "end_date", "posting_date", "as_of_date",
                         "attendance_date"):
            out[field] = today()
        elif lowered == "company":
            company = None
            try:
                company = frappe.defaults.get_user_default("Company")
            except Exception:  # noqa: BLE001 - default lookup is best-effort
                company = None
            if company:
                out[field] = company
    return out


def missing_placeholders(query: str, filters: Mapping) -> list[str]:
    """Return placeholders absent from the request; explicit empty strings are valid SQL values."""
    return sorted({
        field for field in _PLACEHOLDER.findall(query or "")
        if field not in filters or filters[field] is None
    })


def normalise_query_report_filters(report_name: str, filters) -> dict:
    """Normalize filters for app-owned Query Reports before SQL interpolation."""
    if not frappe.db.exists("Report", report_name):
        return filters or {}

    doc = frappe.get_cached_doc("Report", report_name)
    if doc.module != "Tradexcel HR" or doc.report_type != "Query Report":
        return filters or {}

    # Filters arrive either as a dict (desk) or as a JSON string (HTTP form
    # encoding, e.g. `filters={}` in a POST body). `dict("{}")` would try to
    # iterate characters, so parse first.
    if isinstance(filters, str):
        try:
            filters = frappe.parse_json(filters) if filters.strip() else {}
        except Exception:  # noqa: BLE001 - fall through to a clear error below
            frappe.throw(frappe._("Report filters must be valid JSON."))
    if not isinstance(filters, Mapping):
        frappe.throw(frappe._("Report filters must be a JSON object."))
    filters = dict(filters)

    defaults = placeholder_defaults(doc.query)
    for field, value in defaults.items():
        if filters.get(field) in (None, ""):
            filters[field] = value

    # Report any placeholder still unsatisfied, as a clear message rather than a
    # driver-level crash inside SQL interpolation. Duplicates are collapsed:
    # a placeholder used five times in the SQL is still one missing filter.
    missing = missing_placeholders(doc.query or "", filters)
    if missing:
        frappe.throw(
            frappe._(
                "This report needs filters that have no safe default: {0}. "
                "Set them in the report's filter bar and run it again."
            ).format(", ".join(missing)),
            title=frappe._("Report filters required"),
        )

    return filters


@frappe.whitelist()
def run(report_name: str, filters=None, **kwargs):
    """Drop-in override of `frappe.desk.query_report.run` for guarded reports.

    Delegates to Frappe unchanged for every other report, so behaviour elsewhere
    is untouched.
    """
    from frappe.desk import query_report

    filters = normalise_query_report_filters(report_name, filters)
    return query_report.run(report_name=report_name, filters=filters, **kwargs)
