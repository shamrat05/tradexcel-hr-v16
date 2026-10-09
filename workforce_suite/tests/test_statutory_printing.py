"""Source-grounded, dependency-free acceptance for statutory print groundwork."""
from __future__ import annotations

from importlib import util
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "workforce_suite" / "workforce_suite"
SPECS = MODULE / "statutory_form_specs.json"


def _renderer():
    path = MODULE / "statutory_print_html.py"
    spec = util.spec_from_file_location("_statutory_print_html_test", path)
    module = util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.render_html


def _layout(form_code: str):
    entry = next(x for x in json.loads(SPECS.read_text())["entries"] if x["id"] == form_code)
    data = {**entry, "form_family": entry["kind"], "title_en": entry["ui_title"],
            "title_bn": "", "header_note": "", "footer_note": ""}
    data["columns"] = [
        dict(field_key=x["field_key"], label_bn=x["label_bn"],
             label_en=x["label_en"], width_weight=x["width_weight"])
        for x in entry["columns"]
    ]
    return data


def test_pdf_catalog_covers_all_catalog_entries():
    catalog = json.loads(SPECS.read_text(encoding="utf-8"))
    forms = catalog["entries"]
    assert len(forms) == 30
    assert len({x["id"] for x in forms}) == 30
    assert catalog["pdfs_audited"] == 28
    assert catalog["pdf_pages"] == 48
    for form in forms:
        if form["source_sha256"] is not None:
            assert re.fullmatch(r"[0-9a-f]{64}", form["source_sha256"])
        assert form["orientation"] in {"Landscape", "Portrait"}
        assert form["kind"] in {"Register", "Document", "Return", "Evidence Only"}
        assert form["legal_approved"] is False
        assert 1 <= len(form["columns"])
        if form["kind"] != "Return":
            assert len(form["columns"]) <= 22


def test_form_39_and_form_40_keep_distinct_register_meanings():
    rows = {x["id"]: x for x in json.loads(SPECS.read_text())["entries"]}
    damage = {x["field_key"] for x in rows["form_39"]["columns"]}
    advance = {x["field_key"] for x in rows["form_40"]["columns"]}
    assert {"damage_reason", "deduction_order", "recovered_on"} <= damage
    assert {"advance_amount_date", "requital_amount", "requital_date"} <= advance
    assert "damage_reason" not in advance
    assert "advance_amount_date" not in damage


def test_shared_pdf_contains_distinct_form_6_and_6a_regions():
    rows = {x["id"]: x for x in json.loads(SPECS.read_text())["entries"]}
    assert rows["form_6"]["source_sha256"] == rows["form_6a"]["source_sha256"]
    assert "distinct" in rows["form_6a"]["field_audit"].lower()
    assert rows["form_6"]["columns"] != rows["form_6a"]["columns"]
    assert rows["rule_353"]["source_sha256"] is None


@pytest.mark.parametrize("form_id", ["form_6", "form_7", "form_8", "form_9", "form_34", "form_38", "form_80", "form_81"])
def test_suggested_forms_render_valid_a4_html(form_id):
    render = _renderer()
    layout = _layout(form_id)
    data = [{x["field_key"]: "SYNTHETIC RECORD" for x in layout["columns"]}]
    html = render(layout, data, company_name="Example Company", from_date="2026-10-01", to_date="2026-10-07")
    assert "@page { size: A4 " + layout["orientation"].lower() in html
    assert "Example Company" in html
    assert "<!doctype html>" in html
    assert "INTERNAL DRAFT" in html
    assert "Government PDF" not in html


def test_statutory_wage_columns_are_not_derived_from_fixed_payroll_rules():
    cols = _layout("form_38")["columns"]
    assert len(cols) == 17
    assert "basic_wage" in [x["field_key"] for x in cols]
    assert "net_pay" in [x["field_key"] for x in cols]
    assert "acknowledgement" in [x["field_key"] for x in cols]


def test_html_escapes_company_user_and_cell_content():
    layout = _layout("form_6")
    layout["header_note"] = '<script>alert("company")</script>'
    layout["footer_note"] = '<b>sign</b>'
    html = _renderer()(
        layout, [{"employee_name": '<img src=x onerror=alert(1)>'}],
        company_name="<private>", from_date="2026-10-01", to_date="2026-10-07"
    )
    assert "<script>" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;private&gt;" in html
    assert "&lt;b&gt;sign&lt;/b&gt;" in html


def test_source_instructions_never_enter_pdf():
    layout = _layout("form_34")
    layout["legal_review_notes"] = "NEVER_PRINT_SOURCE_INSTRUCTIONS"
    layout["source_url"] = "https://internal.example/NEVER_PRINT_SOURCE_INSTRUCTIONS"
    layout["source_issue"] = "NEVER_PRINT_SOURCE_INSTRUCTIONS"
    html = _renderer()(layout, [], company_name="Example", from_date="2026-10-01", to_date="2026-10-07")
    assert "NEVER_PRINT_SOURCE_INSTRUCTIONS" not in html


def test_externally_issued_certificate_cannot_be_generated():
    layout = _layout("form_32")
    with pytest.raises(ValueError, match="cannot be generated"):
        _renderer()(layout, [], company_name="Example")


def test_wide_register_cannot_render_in_a4_portrait():
    layout = _layout("form_38")
    layout["orientation"] = "Portrait"
    with pytest.raises(ValueError, match="landscape"):
        _renderer()(layout, [], company_name="Example")


def test_many_rows_use_repeating_headers_and_no_fixed_row_height():
    layout = _layout("form_38")
    rows = [{"employee_name": f"SYN-EMP-{i:04}", "net_pay": str(i)} for i in range(150)]
    html = _renderer()(layout, rows, company_name="Example")
    assert html.count("SYN-EMP-") == 150
    assert "display:table-header-group" in html
    assert "page-break-inside:avoid" in html
    assert "table-layout:fixed" in html
    assert "height:" not in html.split("table {width:", 1)[1].split("thead", 1)[0]


def test_print_layout_controllers_enforce_review_and_access_checks():
    parent = MODULE / "doctype" / "workforce_statutory_print_layout"
    src = (parent / "workforce_statutory_print_layout.py").read_text()
    assert "check_company(" in src
    assert 'source["legal_approved"]' in src
    assert "before_submit" in src
    rec = (MODULE / "doctype" / "workforce_statutory_record" / "workforce_statutory_record.py").read_text()
    assert "check_company(" in rec
    assert 'layout.check_permission("read")' in rec


# Export UX policy is deliberately independent of any Frappe database.
from workforce_suite.workforce_suite.statutory_export_policy import (
    available_languages, normalize_period, period_mode, validate_language,
)


def test_employee_documents_use_employee_scope_without_date_prompt():
    assert period_mode("form_6", "Employee") == "none"
    assert period_mode("form_8", "Employee") == "none"
    assert normalize_period("form_6", "Employee", None, None) == ("", "")


def test_attendance_form_week_is_friday_to_thursday_only():
    assert period_mode("form_34", "Attendance") == "week"
    assert normalize_period("form_34", "Attendance", "2026-10-02", "2026-10-08") == (
        "2026-10-02", "2026-10-08"
    )
    with pytest.raises(ValueError, match="Friday-Thursday"):
        normalize_period("form_34", "Attendance", "2026-10-03", "2026-10-09")
    with pytest.raises(ValueError, match="Friday-Thursday"):
        normalize_period("form_34", "Attendance", "2026-10-01", "2026-10-31")


def test_period_reports_keep_existing_custom_range_without_another_period_type():
    assert period_mode("form_38", "Salary Slip") == "range"
    assert normalize_period("form_38", "Salary Slip", "2026-10-01", "2026-10-31") == (
        "2026-10-01", "2026-10-31"
    )


def test_bn_export_requires_complete_translations_without_english_fallback():
    layout = _layout("form_34")
    layout["title_bn"] = "হাজিরা ও অতিরিক্ত সময়"
    assert available_languages(layout) == ("en", "bn")
    assert validate_language(layout, "bn") == "bn"
    html = _renderer()(layout, [{"employee_name": "Synthetic"}],
                       company_name="Example Company", language="bn")
    assert 'lang="bn"' in html
    assert "হাজিরা ও অতিরিক্ত সময়" in html
    assert "অভ্যন্তরীণ খসড়া" in html
    assert '<th scope="col">Worker name' not in html

    layout["columns"][0]["label_bn"] = ""
    assert available_languages(layout) == ("en",)
    with pytest.raises(ValueError, match="Bangla"):
        _renderer()(layout, [], company_name="Example Company", language="bn")


def test_en_export_has_only_en_headers_and_html_language():
    layout = _layout("form_34")
    layout["title_bn"] = "হাজিরা"
    html = _renderer()(layout, [], company_name="Example Company", language="en")
    assert 'lang="en"' in html
    assert '<th scope="col">Worker name' in html
    assert "হাজিরা" not in html



def test_docx_working_copy_a4_orientation_language_and_no_source_instructions():
    from io import BytesIO
    from docx import Document
    from docx.shared import Mm
    from workforce_suite.workforce_suite.statutory_print_docx import render_docx

    layout = _layout("form_34")
    layout["title_bn"] = "হাজিরা ও অতিরিক্ত সময়"
    layout["source_issue"] = "NEVER_LEAK_GOVERNMENT_INSTRUCTIONS"
    source = [{"employee_name": "EMP-01", "day_fri": "8"},
              {"employee_name": "EMP-02", "day_fri": "6"}]
    result = render_docx(layout, source, company_name="Example", language="bn")
    assert result[:2] == b"PK"
    written = Document(BytesIO(result))
    section = written.sections[0]
    assert abs(section.page_width.mm - 297) < 1
    assert abs(section.page_height.mm - 210) < 1
    text = "\n".join(p.text for p in written.paragraphs)
    assert "হাজিরা ও অতিরিক্ত সময়" in text
    assert "সরকারি দাখিল নয়" in text
    assert "NEVER_LEAK" not in text
    joined = "\n".join(cell.text for table in written.tables for row in table.rows for cell in row.cells)
    assert "EMP-01" in joined and "EMP-02" in joined


def test_docx_portrait_document_and_wide_register_keep_all_columns():
    from io import BytesIO
    from docx import Document
    from workforce_suite.workforce_suite.statutory_print_docx import render_docx

    layout = _layout("form_6")
    output = Document(BytesIO(render_docx(
        layout, [{"employee_name": "SYN-001"}], company_name="Example"
    )))
    assert abs(output.sections[0].page_width.mm - 210) < 1
    assert "SYN-001" in "\n".join(
        cell.text for t in output.tables for row in t.rows for cell in row.cells
    )
    wide = _layout("form_38")
    rendered = Document(BytesIO(render_docx(wide, [
        {x["field_key"]: f"VALUE-{x['field_key']}" for x in wide["columns"]}
    ], company_name="Example")))
    docx_body = "\n".join(
        cell.text for t in rendered.tables for row in t.rows for cell in row.cells
    )
    assert all(f"VALUE-{x['field_key']}" in docx_body for x in wide["columns"])
    assert max(len(t.columns) for t in rendered.tables) <= 8


def test_native_sources_cannot_be_relabelled_as_manual_statutory_forms():
    controller = (
        MODULE / "doctype" / "workforce_statutory_print_layout" /
        "workforce_statutory_print_layout.py"
    ).read_text()
    assert 'self.data_source != source["data_source"]' in controller
    assert 'layout.data_source != spec["data_source"]' in (MODULE / "statutory_forms.py").read_text()
    record = (
        MODULE / "doctype" / "workforce_statutory_record" /
        "workforce_statutory_record.py"
    ).read_text()
    assert 'layout.data_source != "Manual"' in record
