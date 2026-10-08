"""Editable A4 Word working copies of company-scoped statutory draft datasets.

The DOCX is intentionally NOT an official government form or licence.
Wide registers are split into manageable column bands (with repeated worker
identifier) rather than being compressed into illegible 17-column Word tables.
There is no Frappe import: tested with synthetic people and entities.
"""
from __future__ import annotations

from io import BytesIO

from workforce_suite.workforce_suite.statutory_export_policy import validate_language


def _value(item, field, default=""):
    return item.get(field, default) if isinstance(item, dict) else getattr(item, field, default)


def _text(value):
    return "" if value is None else str(value)


def _table(doc, labels, keys, rows):
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt

    table = doc.add_table(rows=1, cols=len(keys))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    for i, title in enumerate(labels):
        table.rows[0].cells[i].text = _text(title)
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    table.rows[0]._tr.get_or_add_trPr().append(tbl_header)
    for values in rows:
        cells = table.add_row().cells
        for i, key in enumerate(keys):
            cells[i].text = _text(values.get(key, ""))
    for row in table.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                para.paragraph_format.space_after = Pt(0)
                for run in para.runs:
                    run.font.size = Pt(8)
    return table


def render_docx(
    layout, rows, *, company_name: str, from_date: str = "",
    to_date: str = "", language: str = "en",
) -> bytes:
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.shared import Mm, Pt

    validate_language(layout, language)
    family = _value(layout, "form_family", "Register")
    if family == "Evidence Only":
        raise ValueError("An externally issued certificate cannot be generated")
    columns = list(_value(layout, "columns", []))
    if not columns or len(columns) > 22:
        raise ValueError("DOCX expects 1-22 reviewed columns")
    orientation = _value(layout, "orientation")
    if orientation not in ("Portrait", "Landscape"):
        raise ValueError("Word print orientation must be A4 Portrait or Landscape")

    doc = Document()
    section = doc.sections[0]
    landscape = orientation == "Landscape"
    section.orientation = WD_ORIENT.LANDSCAPE if landscape else WD_ORIENT.PORTRAIT
    section.page_width = Mm(297 if landscape else 210)
    section.page_height = Mm(210 if landscape else 297)
    section.left_margin = section.right_margin = Mm(10)
    section.top_margin = Mm(12)
    section.bottom_margin = Mm(13)

    style = doc.styles["Normal"]
    style.font.name = "Nirmala UI" if language == "bn" else "Arial"
    style.font.size = Pt(9)
    style.paragraph_format.space_after = Pt(4)

    suffix = "বাংলা সম্পাদনাযোগ্য খসড়া — সরকারি দাখিল নয়" if language == "bn" else "EDITABLE WORKING COPY — NOT AN OFFICIAL FILING"
    doc.add_heading(_text(_value(layout, "title_bn" if language == "bn" else "title_en")), 1)
    doc.add_paragraph(_text(company_name))
    if from_date and to_date:
        prefix = "সময়কাল" if language == "bn" else "Period"
        doc.add_paragraph(f"{prefix}: {from_date} — {to_date}")
    doc.add_paragraph(suffix)
    if _value(layout, "header_note"):
        doc.add_paragraph(_text(_value(layout, "header_note")))

    keys = [_text(_value(col, "field_key")) for col in columns]
    labels = [_text(_value(col, "label_bn" if language == "bn" else "label_en")) for col in columns]
    data = list(rows)
    if family == "Register":
        # Never shrink a 16/22-column PDF grid into an unreadable Word table.
        # Every column is retained: for wide forms, repeat an identifying
        # column alongside consecutive bands of at most seven other fields.
        if len(keys) <= 8:
            _table(doc, labels, keys, data)
        else:
            key_index = next(
                (i for i, key in enumerate(keys) if key in ("employee_name", "employee", "worker_register_no", "serial_no")),
                0,
            )
            anchor = keys[key_index]
            anchor_label = labels[key_index]
            remaining = [(key, label) for i, (key, label) in enumerate(zip(keys, labels)) if i != key_index]
            for offset in range(0, len(remaining), 6):
                if offset:
                    doc.add_page_break()
                batch = remaining[offset:offset + 6]
                heading = "কলাম" if language == "bn" else "Fields"
                doc.add_paragraph(f"{heading} {offset + 1}–{offset + len(batch)}")
                _table(
                    doc,
                    [anchor_label] + [label for _, label in batch],
                    [anchor] + [key for key, _ in batch],
                    data,
                )
    else:
        # Per-person letters and narrative returns read best as editable
        # label/value Word sections; one row is one complete document.
        items = data or [{}]
        for index, item in enumerate(items):
            if index:
                doc.add_page_break()
            _table(
                doc, ["বিষয়" if language == "bn" else "Field",
                      "তথ্য" if language == "bn" else "Value"],
                ["label", "value"],
                [{"label": label, "value": _text(item.get(key))} for key, label in zip(keys, labels)],
            )
    if _value(layout, "footer_note"):
        doc.add_paragraph(_text(_value(layout, "footer_note")))

    stream = BytesIO()
    doc.save(stream)
    return stream.getvalue()
