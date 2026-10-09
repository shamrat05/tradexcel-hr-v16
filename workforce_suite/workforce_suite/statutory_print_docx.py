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
    to_date: str = "", language: str = "en", company_address: str = "", signatory: str = "",
    company_logo: str = "", company_logo_bytes: bytes = b"", letter_head_content: str = "", letter_head_footer: str = "",
) -> bytes:
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.shared import Mm, Pt, RGBColor

    validate_language(layout, language)
    family = _value(layout, "form_family", "Register")
    if family == "Evidence Only":
        raise ValueError("An externally issued certificate cannot be generated")
    columns = list(_value(layout, "columns", []))
    if not columns or (len(columns) > 22 and family == "Register"):
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
    style.font.name = "Noto Sans Bengali" if language == "bn" else "Arial"
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
    fonts.set(qn("w:cs"), style.font.name)
    fonts.set(qn("w:eastAsia"), style.font.name)
    style.font.size = Pt(9)
    style.paragraph_format.space_after = Pt(4)
    for heading_name in ("Heading 1", "Heading 2"):
        heading = doc.styles[heading_name]
        heading.font.name = style.font.name
        heading.font.color.rgb = RGBColor(0, 0, 0)
        heading_fonts = heading.element.get_or_add_rPr().get_or_add_rFonts()
        for language_font in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            heading_fonts.set(qn(language_font), style.font.name)

    if company_logo_bytes:
        picture = doc.add_picture(BytesIO(company_logo_bytes), width=Mm(42))
        if picture.height > Mm(18):
            picture.width = int(picture.width * Mm(18) / picture.height)
            picture.height = Mm(18)
    suffix = "বাংলা সম্পাদনাযোগ্য খসড়া — সরকারি দাখিল নয়" if language == "bn" else "EDITABLE WORKING COPY — NOT AN OFFICIAL FILING"
    if letter_head_content:
        from re import sub
        doc.add_paragraph(_text(sub("<[^>]+>", " ", letter_head_content)).strip())
    doc.add_heading(_text(_value(layout, "title_bn" if language == "bn" else "title_en")), 1)
    doc.add_paragraph(_text(company_name))
    if company_address:
        doc.add_paragraph(_text(company_address))
    if from_date and to_date:
        prefix = "সময়কাল" if language == "bn" else "Period"
        doc.add_paragraph(f"{prefix}: {from_date} — {to_date}")
    doc.add_paragraph(suffix)
    header_key = "header_note_bn" if language == "bn" else "header_note"
    footer_key = "footer_note_bn" if language == "bn" else "footer_note"
    if _value(layout, header_key):
        doc.add_paragraph(_text(_value(layout, header_key)))

    header_columns = [c for c in columns if _value(c,"section_key") == "header"] if family == "Register" else []
    columns = [c for c in columns if c not in header_columns]
    keys = [_text(_value(col, "field_key")) for col in columns]
    labels = [_text(_value(col, "label_bn" if language == "bn" else "label_en")) for col in columns]
    data = list(rows)
    if family == "Register":
        groups = {}
        for item in data:
            identity = ""
            if _value(layout, "form_code") == "form_9":
                identity = " · ".join(_text(item.get(key)) for key in ("employee_name", "worker_register_no", "card_no", "designation", "department", "date_of_joining"))
            if header_columns:
                identity = ' · '.join(_text(_value(c,"label_bn" if language=='bn' else "label_en")) + ': ' + _text(item.get(_value(c,"field_key"))) for c in header_columns)
            groups.setdefault(identity, []).append(item)
        if not groups:
            groups[""] = []
        original_keys, original_labels = list(keys), list(labels)
        for group_index, (identity, data) in enumerate(groups.items()):
            keys, labels = list(original_keys), list(original_labels)
            if group_index:
                doc.add_page_break()
            if identity:
                doc.add_paragraph(identity)
            # Never shrink a 16/22-column PDF grid into an unreadable Word table.
            # Every column is retained: for wide forms, repeat an identifying
            # column alongside consecutive bands of at most seven other fields.
            if len(keys) <= 8:
                _table(doc, labels, keys, data)
            else:
                if "serial_no" not in keys:
                    data = [{**row, "_row_reference": i} for i, row in enumerate(data, 1)]
                    keys = ["_row_reference"] + keys
                    labels = ["সারির নির্দেশক" if language == "bn" else "Working-copy row reference"] + labels
                key_index = next(
                    (i for i, key in enumerate(keys) if key in ("serial_no", "_row_reference")),
                    0,
                )
                anchor = keys[key_index]
                anchor_label = labels[key_index]
                remaining = [(key, label) for i, (key, label) in enumerate(zip(keys, labels)) if i != key_index]
                for offset in range(0, len(remaining), 6):
                    if offset:
                        doc.add_page_break()
                        if identity:
                            doc.add_paragraph(identity)
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
        index = 0
        groups = {}
        for column in columns:
            groups.setdefault(_value(column, "section_key"), []).append(column)
        for item in items:
            for section_key, group in groups.items():
                if index:
                    doc.add_page_break()
                index += 1
                title = _value(group[0], "section_bn" if language == "bn" else "section_en")
                if title:
                    doc.add_heading(_text(title), 2)
                if section_key in {"front", "identity"} and item.get("_portrait_bytes"):
                    portrait = doc.add_picture(BytesIO(item["_portrait_bytes"]), width=Mm(30))
                    if portrait.height > Mm(38):
                        portrait.width = int(portrait.width * Mm(38) / portrait.height)
                        portrait.height = Mm(38)
                from workforce_suite.workforce_suite.statutory_structure import matrices_for, matrix_keys, repeatable_for, history_pages
                matrices = matrices_for(_value(layout, "form_code"), section_key)
                repeated = repeatable_for(_value(layout, "form_code"), section_key)
                consumed = matrix_keys(matrices) | {key for table in repeated for key in table["keys"]}
                _table(doc, ["বিষয়" if language == "bn" else "Field", "তথ্য" if language == "bn" else "Value"],
                       ["label", "value"], [{"label": _value(c, "label_bn" if language == "bn" else "label_en"),
                       "value": _text(item.get(_value(c, "field_key")))} for c in group if _value(c, "field_key") not in consumed])
                for matrix in matrices:
                    suffix = "bn" if language == "bn" else "en"
                    doc.add_heading(matrix["title_" + suffix], 2)
                    keys = ["category"] + [str(i) for i in range(len(matrix["column_labels_" + suffix]))]
                    values = [{"category": label, **{str(i): item.get(key) for i, key in enumerate(fields)}}
                              for label, fields in zip(matrix["row_labels_" + suffix], matrix["cells"])]
                    _table(doc, ["শ্রেণি" if language == "bn" else "Category"] + matrix["column_labels_" + suffix], keys, values)
                for repeated_table in repeated:
                    keys = repeated_table["keys"]
                    labels = {_value(c, "field_key"): _value(c, "label_bn" if language == "bn" else "label_en") for c in group}
                    records = item.get("_history", {}).get(repeated_table["id"], [])
                    bands = [keys] if len(keys) <= 7 else [[keys[0]] + keys[offset:offset+6] for offset in range(1, len(keys), 6)]
                    if not records:
                        doc.add_paragraph("পর্যালোচিত ইতিহাস প্রয়োজন" if language == "bn" else "Reviewed history required")
                    for page_index, page_rows in enumerate(history_pages(repeated_table, records)):
                        if page_index:
                            doc.add_page_break()
                            doc.add_heading(repeated_table["title_bn" if language == "bn" else "title_en"], 2)
                        for band in bands:
                            _table(doc, [labels[key] for key in band], band, page_rows or [{}])
    from workforce_suite.workforce_suite.statutory_structure import financial_appendices
    for appendix_title, keys, labels, records in financial_appendices(rows, language):
        doc.add_page_break()
        doc.add_heading(appendix_title, 2)
        _table(doc, labels, keys, records)
    if letter_head_footer:
        from re import sub
        doc.add_paragraph(_text(sub("<[^>]+>", " ", letter_head_footer)).strip())
    if _value(layout, footer_key):
        doc.add_paragraph(_text(_value(layout, footer_key)))
    page_number = OxmlElement("w:fldSimple")
    page_number.set(qn("w:instr"), "PAGE")
    if signatory:
        doc.add_paragraph(_text(signatory))
    section.footer.paragraphs[0]._p.append(page_number)

    stream = BytesIO()
    doc.save(stream)
    return stream.getvalue()
