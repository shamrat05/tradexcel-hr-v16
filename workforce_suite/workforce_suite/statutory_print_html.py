"""Pure HTML renderer for validated statutory paper and card layouts.

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


def render_html(
    layout: object,
    rows: list[dict],
    *,
    company_name: str,
    company_address: str = "",
    signatory: str = "",
    company_logo: str = "",
    letter_head_content: str = "",
    letter_head_footer: str = "",
    from_date: str = "",
    to_date: str = "",
    is_draft: bool = True,
    language: str = "en",
    page_setup: dict | None = None,
) -> str:
    """Produce the same validated physical page geometry as PDF and DOCX."""
    from workforce_suite.workforce_suite.statutory_export_policy import validate_language
    from workforce_suite.workforce_suite.statutory_page_setup import resolve_page_setup

    language = validate_language(layout, language)
    page = page_setup or resolve_page_setup(layout)
    family = str(_entry(layout, "form_family", "Register"))
    if family == "Evidence Only":
        raise ValueError("An externally issued certificate cannot be generated")
    columns = list(_entry(layout, "columns", []))
    if not columns:
        raise ValueError("Print layout has no approved columns")
    if len(columns) > 22 and family == "Register":
        raise ValueError("No more than 22 columns per table")
    if len(columns) > 11 and page["width_mm"] - 2 * page["margin_mm"] < 270 and family == "Register":
        raise ValueError("Wide register needs at least 270 mm printable width")

    header_columns = [c for c in columns if _entry(c, "section_key") == "header"] if family == "Register" else []
    columns = [c for c in columns if c not in header_columns]
    widths = [max(1, min(5, int(_entry(c, "width_weight", 1) or 1))) for c in columns]
    total = sum(widths)
    percents = [100.0 * w / total for w in widths]

    translated = language == "bn"
    title = _safe(_entry(layout, "title_bn" if translated else "title_en") or "")
    subtitle = _safe(_entry(layout, "header_note_bn" if translated else "header_note", "") or "")
    footer = _safe(_entry(layout, "footer_note_bn" if translated else "footer_note", "") or "")
    name = _safe(company_name)
    address = _safe(company_address)
    period = (_safe(from_date) + " — " + _safe(to_date)) if from_date and to_date else ""
    period_label = "সময়কাল" if translated else "Period"
    draft_label = (
        "অভ্যন্তরীণ খসড়া — সরকারি দাখিলের জন্য নয়"
        if translated else "INTERNAL DRAFT — NOT AN OFFICIAL FILING"
    )
    branding = ""
    logo_html = ('<img class="company-logo" src="' + _safe(company_logo) + '" alt="Company logo">') if company_logo and page["logo_position"] != "Hidden" else ""
    if page["logo_position"] == "Left":
        branding += logo_html
    if letter_head_content and not page["is_card"]:
        branding += '<div class="letter-head-content">' + letter_head_content + '</div>'
    heading = (
        '<header><div class="heading-left">' + branding + '<h1>' + title + '</h1></div>'
        + '<div class="heading-right">' + (logo_html if page["logo_position"] == "Right" else "") + '<strong>' + name + '</strong>'
        + (f"<span>{address}</span>" if address and not page["is_card"] else "")
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
        groups = {}
        for row in rows:
            identity = row.get("employee", "") if _entry(layout, "form_code") == "form_9" else ""
            if header_columns:
                identity = tuple(str(row.get(_entry(c,"field_key")) or "") for c in header_columns)
            groups.setdefault(identity, []).append(row)
        if not groups:
            groups[""] = []
        tables = []
        for identity, records in groups.items():
            body = []
            for row in records:
                cells = "".join("<td>" + _safe(row.get(str(_entry(col, "field_key", "")), "")) + "</td>" for col in columns)
                body.append("<tr>" + cells + "</tr>")
            if not records:
                empty_label = "এই সময়ের জন্য কোনো যাচাইকৃত রেকর্ড নেই।" if translated else "No verified records for this period."
                body = [f'<tr><td colspan="{len(columns)}" class="empty">{empty_label}</td></tr>']
            worker = ""
            if identity and _entry(layout, "form_code") == "form_9":
                row = records[0]
                pairs = [("employee_name", "Worker", "শ্রমিক"), ("worker_register_no", "Worker register number", "শ্রমিকের রেজিস্টার নম্বর"),
                         ("card_no", "Card number", "কার্ড নম্বর"), ("designation", "Designation", "পদবি"),
                         ("department", "Department", "বিভাগ"), ("date_of_joining", "Joining date", "নিয়োগের তারিখ")]
                worker = '<p class="company-note">' + " · ".join(_safe(bn if translated else en) + ": " + _safe(row.get(key)) for key, en, bn in pairs) + '</p>'
            if header_columns and records:
                worker += '<p class="company-note">' + ' · '.join(_safe(_entry(c, "label_bn" if translated else "label_en")) + ': ' + _safe(records[0].get(_entry(c,"field_key"))) for c in header_columns) + '</p>'
            tables.append('<section class="leave-entry">' + worker + "<table><colgroup>" + colgroups + "</colgroup><thead><tr>" + heads + "</tr></thead><tbody>" + "".join(body) + "</tbody></table></section>")
        table = "".join(tables)
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
            sections = {}
            for col in columns:
                section = str(_entry(col, "section_key", ""))
                sections.setdefault(section, []).append(col)
            from workforce_suite.workforce_suite.statutory_structure import matrices_for, matrix_keys, repeatable_for, history_pages
            for section, section_columns in sections.items():
                matrices = matrices_for(_entry(layout, "form_code"), section)
                repeated = repeatable_for(_entry(layout, "form_code"), section)
                consumed = matrix_keys(matrices) | {key for table in repeated for key in table["keys"]}
                cells = "".join(
                    '<tr><th scope="row">' + _safe(_entry(col, "label_bn" if translated else "label_en"))
                    + '</th><td>' + _safe(row.get(str(_entry(col, "field_key", "")), "")) + '</td></tr>'
                    for col in section_columns if _entry(col, "field_key") not in consumed)
                matrix_html = ""
                if _entry(layout, "form_code") in {"form_6", "form_7"} and section in {"front", "identity"} and row.get("_portrait_bytes"):
                    import base64
                    encoded = base64.b64encode(row["_portrait_bytes"]).decode("ascii")
                    mime = "image/png" if row["_portrait_bytes"].startswith(b"\x89PNG") else "image/jpeg"
                    matrix_html += '<img class="worker-portrait" src="data:' + mime + ';base64,' + encoded + '" alt="Worker portrait">'
                for matrix in matrices:
                    suffix = "bn" if translated else "en"
                    heads = '<th></th>' + ''.join('<th>' + _safe(label) + '</th>' for label in matrix['column_labels_' + suffix])
                    body = ''.join('<tr><th>' + _safe(label) + '</th>' + ''.join('<td>' + _safe(row.get(key)) + '</td>' for key in keys) + '</tr>'
                                   for label, keys in zip(matrix['row_labels_' + suffix], matrix['cells']))
                    matrix_html += '<h3>' + _safe(matrix['title_' + suffix]) + '</h3><table><thead><tr>' + heads + '</tr></thead><tbody>' + body + '</tbody></table>'
                for repeated_table in repeated:
                    records = row.get("_history", {}).get(repeated_table["id"], [])
                    keys = repeated_table["keys"]
                    labels = {str(_entry(c, "field_key")): _entry(c, "label_bn" if translated else "label_en") for c in section_columns}
                    bands = [keys] if len(keys) <= 7 else [[keys[0]] + keys[offset:offset+6] for offset in range(1, len(keys), 6)]
                    for page_index, page_rows in enumerate(history_pages(repeated_table, records)):
                        if page_index:
                            matrix_html += '<div class="book-continuation"><h2>' + _safe(repeated_table["title_bn" if translated else "title_en"]) + '</h2></div>'
                        for band in bands:
                            heads = ''.join('<th>' + _safe(labels[key]) + '</th>' for key in band)
                            body = ''.join('<tr>' + ''.join('<td style="height:8mm">' + _safe(record.get(key)) + '</td>' for key in band) + '</tr>' for record in page_rows)
                            if not page_rows:
                                body = '<tr>' + ''.join('<td style="height:18mm"></td>' for key in band) + '</tr>'
                            matrix_html += '<table><thead><tr>' + heads + '</tr></thead><tbody>' + body + '</tbody></table>'
                section_heading = _safe(_entry(section_columns[0], "section_bn" if translated else "section_en", ""))
                contents = '<table class="key-value"><tbody>' + cells + '</tbody></table>'
                contents = (matrix_html + contents) if page["is_card"] else (contents + matrix_html)
                pages.append('<section class="document-entry">' + (f'<h2>{section_heading}</h2>' if section_heading else '')
                             + contents + '</section>')
        table = "".join(pages)
    from workforce_suite.workforce_suite.statutory_structure import financial_appendices
    for appendix_title, keys, labels, records in financial_appendices(rows, language):
        heads = ''.join('<th>' + _safe(label) + '</th>' for label in labels)
        body = ''.join('<tr>' + ''.join('<td>' + _safe(record.get(key)) + '</td>' for key in keys) + '</tr>' for record in records)
        table += '<section class="leave-entry"><h2>' + _safe(appendix_title) + '</h2><table><thead><tr>' + heads + '</tr></thead><tbody>' + body + '</tbody></table></section>'
    footer = "\n".join(value for value in (letter_head_footer, footer, _safe(signatory)) if value)
    foot = f'<footer class="signatory">{footer}</footer>' if footer else ""
    density = "dense" if len(columns) >= 14 and family == "Register" else "normal"
    css = """
@page { size: PAGE_WIDTHmm PAGE_HEIGHTmm; margin: PAGE_MARGINmm; }
html, body {margin:0; padding:0; background:#fff; color:#151515; }
body {font-family:"Noto Sans Bengali","Nirmala UI",Arial,sans-serif;
      font-size:9pt; line-height:1.34; -webkit-print-color-adjust:exact; }
* {box-sizing:border-box;}
header {display:table; width:100%; border-bottom:1.2pt solid #171717;
        padding:0 0 3mm; margin:0 0 3mm;}
.heading-left,.heading-right {display:table-cell; vertical-align:top;}
.company-logo {display:block; max-width:42mm; max-height:18mm; object-fit:contain; margin-bottom:2mm;}
.heading-right .company-logo {margin-left:auto;}
.worker-portrait {width:30mm;max-height:38mm;object-fit:contain;}
.watermark {position:fixed;top:44%;left:8%;width:84%;text-align:center;z-index:0;
            font-size:32pt;color:#dedede;opacity:.42;transform:rotate(-25deg);pointer-events:none;}
header,.document-entry,.leave-entry,.signatory {position:relative;z-index:1;}
.letter-head-content {font-size:8.5pt; margin-bottom:2mm;}
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
.dense th {font-size:8.5pt; padding:1.2mm .65mm;}
.dense td {font-size:9pt; padding:1.2mm .75mm;}
.dense th small {font-size:6pt;}
.key-value {table-layout:fixed;}
.key-value th {width:32%; font-size:9pt;}
.key-value td {font-size:9pt;}
.document-entry {break-after:page; page-break-after:always;}
.document-entry:last-child {break-after:auto; page-break-after:auto;}
.book-continuation {break-before:page; page-break-before:always;}
.leave-entry + .leave-entry {break-before:page; page-break-before:always;}
h2 {font-size:11pt; margin:0 0 3mm;}
.empty {text-align:center; font-style:italic; padding:6mm;}
.signatory {margin-top:12mm; padding-top:4mm; border-top:.65pt solid #bbb;
            text-align:right; font-size:9pt; white-space:pre-wrap;}
@media screen {
  body {margin:16px auto; padding:12px; width:PAGE_WIDTHmm; max-width:100%;
        border:1px solid #ccc; box-shadow:0 4px 18px #ddd;}
}
""".replace("PAGE_WIDTH", str(page["width_mm"])).replace("PAGE_HEIGHT", str(page["height_mm"])).replace("PAGE_MARGIN", str(page["margin_mm"]))
    if page["layout_style"] == "Compact":
        css += "\nbody {font-size:8pt;line-height:1.2;} th,td {padding:1mm .8mm;} h1 {font-size:11pt;}\n"
    if page["is_card"]:
        css += """
body {font-size:5.8pt;line-height:1.08;}
header {margin-bottom:1mm;padding-bottom:.5mm;}
h1 {font-size:7pt;line-height:1.1;}
h2 {font-size:6pt;margin:0 0 .5mm;}
.heading-right {font-size:5.5pt;width:32%;}
.company-logo {max-width:16mm;max-height:6mm;margin-bottom:.3mm;}
.worker-portrait {float:right;width:17mm;max-height:22mm;margin:0 0 .5mm 1mm;}
.document-entry {padding:0;margin:0;overflow:visible;}
.key-value th {width:37%;font-size:5.3pt;}
.key-value td {font-size:5.3pt;}
th,td {padding:.23mm .38mm;border:.35pt solid #555;line-height:1.05;}
.draft {font-size:5pt;padding:.4mm;margin:.4mm 0;}
.company-note {font-size:5pt;margin:0 0 .5mm;}
.signatory {font-size:5pt;margin-top:1mm;padding-top:.4mm;}
.watermark {font-size:12pt;}
"""
        if page["width_mm"] >= 130:
            css += """
body {font-size:7pt;line-height:1.1;}
h1 {font-size:8.2pt;}
h2 {font-size:7pt;}
.heading-right {font-size:6.5pt;}
.key-value th,.key-value td {font-size:6.5pt;}
.draft,.company-note,.signatory {font-size:6pt;}
"""
    watermark = ('<div class="watermark" aria-hidden="true">' + _safe(page["watermark_text"]) + '</div>') if page["watermark_text"] else ""
    return (
        '<!doctype html><html lang="' + language + '"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>' + css + '</style></head>'
        '<body class="' + density + '">' + watermark + heading + table + foot + '</body></html>'
    )
