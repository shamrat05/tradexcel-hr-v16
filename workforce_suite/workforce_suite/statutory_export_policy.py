"""Context-sensitive period, language and scope rules for Bangladesh print drafts.

Pure functions (no Frappe imports) so the same rules can be tested without a
live site. Form-specific constraints come from document semantics, not hardcoded
customer configuration.
"""
from __future__ import annotations

from datetime import date


SUPPORTED_LANGUAGES = ("en", "bn")
NO_PERIOD_SOURCES = frozenset({"Employee"})
WEEKLY_FORM = "form_34"


def period_mode(form_code: str, data_source: str) -> str:
    """The UX must not ask for dates where dates have no meaning."""
    if data_source in NO_PERIOD_SOURCES:
        return "none"
    if form_code == WEEKLY_FORM:
        return "week"
    if form_code == "form_80":
        return "half-year"
    if form_code == "form_81":
        return "year"
    return "range"


def _iso(raw: str, label: str) -> date:
    try:
        return date.fromisoformat(str(raw))
    except (ValueError, TypeError) as error:
        raise ValueError(f"{label} must be a valid YYYY-MM-DD date") from error


def normalize_period(
    form_code: str,
    data_source: str,
    from_date: str | None,
    to_date: str | None,
) -> tuple[str, str]:
    mode = period_mode(form_code, data_source)
    if mode == "none":
        # A worker ID or service book is selected by employee, not by payroll
        # month. Ignore leftover report filters rather than presenting dates.
        return "", ""
    if not from_date or not to_date:
        raise ValueError("Choose a reporting period")
    start = _iso(from_date, "From Date")
    end = _iso(to_date, "To Date")
    if start > end or (end - start).days > 370:
        raise ValueError("Select a valid period of at most 371 days")
    if form_code == "form_80" and not (
        start.year == end.year and ((start.month, start.day, end.month, end.day) in
                                   {(1, 1, 6, 30), (7, 1, 12, 31)})
    ):
        raise ValueError("Form 80 requires a complete January-June or July-December half-year")
    if form_code == "form_81" and not (
        start.year == end.year and (start.month, start.day, end.month, end.day) == (1, 1, 12, 31)
    ):
        raise ValueError("Form 81 requires one complete calendar year")
    if mode == "week":
        # Form 34's ordered day columns are Friday ... Thursday.
        if start.weekday() != 4 or (end - start).days != 6:
            raise ValueError(
                "Form 34 is a Friday-Thursday weekly register. "
                "For monthly or custom-range analysis use the native attendance report; "
                "do not mislabel it as Form 34."
            )
    return start.isoformat(), end.isoformat()


def available_languages(layout: object) -> tuple[str, ...]:
    def get(item: object, key: str) -> str:
        value = item.get(key, "") if isinstance(item, dict) else getattr(item, key, "")
        return str(value or "").strip()
    if not get(layout, "title_en"):
        return ()
    columns = layout.get("columns", []) if isinstance(layout, dict) else getattr(layout, "columns", [])
    if not columns or any(not get(col, "label_en") for col in columns):
        return ()
    english = ("en",)
    notes_translated = all(not get(layout, field) or get(layout, field + "_bn")
                           for field in ("header_note", "footer_note"))
    sections_translated = all(not get(col, "section_key") or get(col, "section_bn") for col in columns)
    if get(layout, "title_bn") and notes_translated and sections_translated and all(get(col, "label_bn") for col in columns):
        return english + ("bn",)
    return english


def validate_language(layout: object, language: str) -> str:
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError("Choose English or Bangla")
    if language not in available_languages(layout):
        raise ValueError(
            "This layout is missing a verified " + (
                "Bangla" if language == "bn" else "English"
            ) + " heading or column label; complete it in the layout editor first"
        )
    return language
