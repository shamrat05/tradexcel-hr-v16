"""Validated, format-neutral physical print settings for statutory working copies.

Presentation options cannot change prescribed fields or the native source data.
Stored layout values are defaults; request overrides apply to one export only.
"""
from __future__ import annotations

import json
import math


PAPER_MM = {
    "A4": (210, 297),
    "A5": (148, 210),
    "A6": (105, 148),
    "A7 Card": (74, 105),
    "Letter": (215.9, 279.4),
    "Legal": (215.9, 355.6),
}
OVERRIDES = frozenset({"paper_size", "orientation", "custom_width_mm", "custom_height_mm",
                       "margin_mm", "logo_position", "watermark_text", "layout_style"})
LOGO_POSITIONS = frozenset({"Left", "Right", "Hidden"})
STYLES = frozenset({"Minimal Black and White", "Compact"})


def _get(item, name, fallback=None):
    return item.get(name, fallback) if isinstance(item, dict) else getattr(item, name, fallback)


def _number(value, label, *, minimum, maximum):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number in millimetres") from None
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum} mm")
    return round(number, 2)


def resolve_page_setup(layout, overrides=None):
    """Return one safe page specification shared by preview, PDF and DOCX."""
    if isinstance(overrides, str):
        try:
            overrides = json.loads(overrides) if overrides else {}
        except (TypeError, ValueError):
            raise ValueError("Print options must be valid JSON") from None
    if not isinstance(overrides or {}, dict):
        raise ValueError("Print options must be an object")
    overrides = overrides or {}
    if set(overrides) - OVERRIDES:
        raise ValueError("Unknown print option")
    code = str(_get(layout, "form_code", ""))
    default_paper = "A7 Card" if code == "form_6" else "A4"
    paper = overrides.get("paper_size") or _get(layout, "paper_size") or default_paper
    if paper not in PAPER_MM and paper != "Custom":
        raise ValueError("Choose a supported paper size")
    default_orientation = "Landscape" if code == "form_6" and not _get(layout, "paper_size") else _get(layout, "orientation")
    orientation = overrides.get("orientation") or default_orientation
    if orientation not in {"Portrait", "Landscape"}:
        raise ValueError("Choose portrait or landscape orientation")
    if paper == "Custom":
        width = _number(overrides.get("custom_width_mm", _get(layout, "custom_width_mm")),
                        "Custom width", minimum=74, maximum=500)
        height = _number(overrides.get("custom_height_mm", _get(layout, "custom_height_mm")),
                         "Custom height", minimum=74, maximum=700)
    else:
        width, height = PAPER_MM[paper]
    if orientation == "Landscape" and width < height:
        width, height = height, width
    elif orientation == "Portrait" and width > height:
        width, height = height, width
    margin = _number(overrides.get("margin_mm", _get(layout, "margin_mm") or (3 if paper == "A7 Card" else 8)),
                     "Margin", minimum=2, maximum=30)
    if margin * 2 >= min(width, height) - 30:
        raise ValueError("Margins leave too little room for the document")
    logo = overrides.get("logo_position") or _get(layout, "logo_position") or "Left"
    if logo not in LOGO_POSITIONS:
        raise ValueError("Choose a supported logo position")
    style = overrides.get("layout_style") or _get(layout, "layout_style") or "Minimal Black and White"
    if style not in STYLES:
        raise ValueError("Choose a supported print style")
    watermark = overrides.get("watermark_text", _get(layout, "watermark_text") or "")
    if not isinstance(watermark, str) or len(watermark) > 60 or any(ord(c) < 32 for c in watermark):
        raise ValueError("Watermark must be one line of at most 60 characters")
    if paper == "A7 Card" and code != "form_6":
        raise ValueError("The card preset is reserved for the two-sided worker identity card")
    if code == "form_6" and (min(width, height) < 74 or max(width, height) < 105):
        raise ValueError("The protected identity-card fields need at least an A7-sized card")
    columns = list(_get(layout, "columns", []) or [])
    family = _get(layout, "form_family", "")
    if family == "Register" and len(columns) > 11 and width - 2 * margin < 270:
        raise ValueError("Wide registers need at least 270 mm of printable width; choose A4 landscape or larger")
    if family == "Register" and width - 2 * margin < 95:
        raise ValueError("This register needs at least 95 mm of printable width")
    return {"paper_size": paper, "orientation": orientation, "width_mm": width,
            "height_mm": height, "margin_mm": margin, "logo_position": logo,
            "watermark_text": watermark, "layout_style": style,
            "is_card": code == "form_6" and width <= 160 and height <= 110}
