"""Pure, dependency-free A4 HTML renderer for configurable statutory layouts.

No DB, Frappe hooks or template code execution here. Every user-supplied
heading/cell is HTML-escaped. Do not print legislation footnotes, source-PDF
instructions, developer notes or evidence-file paths into company documents.
"""
from __future__ import annotations

from html import escape
import re


def _safe(value: object) -> str:
    if value is None:
        return ""
    return escape(str(value), quote=True)


def _entry(row: object, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _sheet(orientation: str) -> str:
    if orientation not in {"Portrait", "Landscape"}:
        raise ValueError("Only A4 Portrait or Landscape is supported")
    return "portrait" if orientation == "Portrait" else "landscape"


def render_html(
    layout: object,
    rows: list[dict],
    *,
    company_name: str,
    company_address: str = "",
    from_date: str = "",
    to_date: str = "",
    is_draft: bool = True,
    language: str = "en",
) -> str:
    """Produce letter-sized document *content* laid out on exact A4 paper.

    The PDF API separately passes explicit page-size and orientation to
    Frappe's converter. Long tables have repeating headers; rows wrap
    instead of shrinking text to illegibility or clipping at the margins.
    """
    from workforce_suite.workforce_suite.statutory_export_policy import validate_language

    language = validate_language(layout, language)
    orientation = _sheet(str(_entry(layout, "orientation", "")))
    family = str(_entry(layout, "form_family", "Register"))
    if family == "Evidence Only":
        raise ValueError("An externally issued certificate cannot be generated")
    columns = list(_entry(layout, "columns", []))
    if not columns:
        raise ValueError("Print layout has no approved columns")
    if len(columns) > 22:
        raise ValueError("A4 safety limit: no more than 22 columns per table")
    if len(columns) > 11 and orientation == "portrait" and family == "Register":
        raise ValueError("Wide register must use landscape A4 or fewer columns")

    widths = [max(1, min(5, int(_entry(c, "width_weight", 1) or 1))) for c in columns]
    total = sum(widths)
    percents = [100.0 * w / total for w in widths]

    translated = language == "bn"
    title = _safe(_entry(layout, "title_bn" if translated else "title_en") or "")
    subtitle = _safe(_entry(layout, "header_note", "") or "")
    footer = _safe(_entry(layout, "footer_note", "") or "")
    name = _safe(company_name)
    address = _safe(company_address)
    period = (_safe(from_date) + " — " + _safe(to_date)) if from_date and to_date else ""
    period_label = "সময়কাল" if translated else "Period"
    draft_label = (
        "অভ্যন্তরীণ খসড়া — সরকারি দাখিলের জন্য নয়"
        if translated else "INTERNAL DRAFT — NOT AN OFFICIAL FILING"
    )
    heading = (
        '<header><div class="heading-left"><h1>' + title + '</h1></div>'
        + '<div class="heading-right"><strong>' + name + '</strong>'
        + (f"<span>{address}</span>" if address else "")
        + (f'<span>{period_label}: {period}</span>' if period else "")
        + "</div></header>"
        + (f'<p class="company-note">{subtitle}</p>' if subtitle else "")
        + (f'<p class="draft">{draft_label}</p>' if is_draft else "")
    )
    # Print column titles only. Source-PDF help/instructions are never added.
    if family == "Register":
        heads = "".join(
            '<th scope="col">' +
            _safe(_entry(col, "label_bn" if translated else "label_en"))
            + "</th>" for col in columns
        )
        colgroups = "".join(f'<col style="width:{width:.5f}%">' for width in percents)
        body = []
        for row in rows:
            cells = "".join(
                "<td>" + _safe(row.get(str(_entry(col, "field_key", "")), "")) + "</td>"
                for col in columns
            )
            body.append("<tr>" + cells + "</tr>")
        if not rows:
            empty_label = "এই সময়ের জন্য কোনো যাচাইকৃত রেকর্ড নেই।" if translated else "No verified records for this period."
            body = [f'<tr><td colspan="{len(columns)}" class="empty">{empty_label}</td></tr>']
        table = "<table><colgroup>" + colgroups + "</colgroup><thead><tr>" + heads + "</tr></thead><tbody>" + "".join(body) + "</tbody></table>"
    else:
        # Single-entry legal letters, certificates and returns benefit from
        # an accessible key/value layout, not a 17-column miniature grid.
        docs = rows if rows else [{}]
        pages = []
        for row in docs:
            cells = "".join(
                '<tr><th scope="row">' +
                _safe(_entry(col, "label_bn" if translated else "label_en"))
                + '</th><td>' + _safe(row.get(str(_entry(col, "field_key", "")), "")) + '</td></tr>'
                for col in columns
            )
            pages.append('<section class="document-entry"><table class="key-value"><tbody>' + cells + '</tbody></table></section>')
        table = "".join(pages)
    foot = f'<footer class="signatory">{footer}</footer>' if footer else ""
    density = "dense" if len(columns) >= 14 and family == "Register" else "normal"
    css = """
@page { size: A4 ORIENTATION; margin: 9mm 8mm 12mm; }
html, body {margin:0; padding:0; background:#fff; color:#151515; }
body {font-family:"Noto Sans Bengali","Nirmala UI",Arial,sans-serif;
      font-size:9pt; line-height:1.34; -webkit-print-color-adjust:exact; }
* {box-sizing:border-box;}
header {display:table; width:100%; border-bottom:1.2pt solid #171717;
        padding:0 0 3mm; margin:0 0 3mm;}
.heading-left,.heading-right {display:table-cell; vertical-align:top;}
.heading-right {text-align:right; width:36%; font-size:8pt;}
.heading-right span {display:block; overflow-wrap:anywhere; padding-top:1mm;}
h1 {font-size:13pt; line-height:1.35; font-weight:700; margin:0;}
.english-title {font-size:9pt; margin:1mm 0 0;}
.company-note {font-size:8.5pt; margin:0 0 2.5mm; white-space:pre-wrap;}
.draft {text-align:center; font-size:8pt; letter-spacing:.3pt;
        border:1px solid #555; padding:2mm; font-weight:700; margin:2mm 0 3mm;}
table {width:100%; border-collapse:collapse; table-layout:fixed; background:#fff;}
thead {display:table-header-group;}
tbody {display:table-row-group;}
tr {page-break-inside:avoid; break-inside:avoid;}
th,td {border:.55pt solid #444; padding:2mm 1.3mm; vertical-align:top;
       overflow-wrap:anywhere; word-break:normal; white-space:pre-wrap;}
th {font-size:8pt; font-weight:700; text-align:left; background:#f5f5f5;}
td {font-size:8pt;}
th small {display:block; font-size:6.5pt; font-weight:400;}
.dense th {font-size:7pt; padding:1.2mm .65mm;}
.dense td {font-size:7.5pt; padding:1.2mm .75mm;}
.dense th small {font-size:6pt;}
.key-value {table-layout:fixed;}
.key-value th {width:32%; font-size:9pt;}
.key-value td {font-size:9pt;}
.document-entry {break-after:page; page-break-after:always;}
.document-entry:last-child {break-after:auto; page-break-after:auto;}
.empty {text-align:center; font-style:italic; padding:6mm;}
.signatory {margin-top:12mm; padding-top:4mm; border-top:.65pt solid #bbb;
            text-align:right; font-size:9pt; white-space:pre-wrap;}
@media screen {
  body {margin:16px auto; padding:12px; max-width:1100px;
        border:1px solid #ccc; box-shadow:0 4px 18px #ddd;}
}
""".replace("ORIENTATION", orientation)
    return (
        '<!doctype html><html lang="' + language + '"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>' + css + '</style></head>'
        '<body class="' + density + '">' + heading + table + foot + '</body></html>'
    )
