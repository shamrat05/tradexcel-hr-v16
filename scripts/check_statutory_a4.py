#!/usr/bin/env python3
"""Render synthetic statutory previews and verify physical A4 page bounds.

Requires weasyprint and PyMuPDF in CI, not in the Frappe server app.
Never uses or writes employee/customer data.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
import sys

import fitz
from weasyprint import HTML

ROOT = Path(__file__).resolve().parents[1]
# Invocation as "python scripts/..." otherwise puts only /scripts on sys.path.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULE = ROOT / "workforce_suite" / "workforce_suite"
SPECS = json.loads((MODULE / "statutory_form_specs.json").read_text())
OUTPUT = ROOT / "build" / "statutory_pdf_qa"


def load_renderer():
    path = MODULE / "statutory_print_html.py"
    spec = importlib.util.spec_from_file_location("_a4_renderer", path)
    loaded = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(loaded)
    return loaded.render_html


def form(code):
    s = next(x for x in SPECS["entries"] if x["id"] == code)
    return {
        **s,
        "form_family": s["kind"],
        "title_en": s["ui_title"],
        "title_bn": "শ্রমিক রেজিস্টার" if code != "form_6" else "পরিচয় পত্র",
        "columns": s["columns"],
    }


def check_pdf(output: Path, orientation: str, expected_id: str):
    doc = fitz.open(output)
    assert len(doc) > 0
    expected = (842, 595) if orientation == "Landscape" else (595, 842)
    for page in doc:
        actual = (page.rect.width, page.rect.height)
        assert all(abs(a-b) < 1.5 for a, b in zip(actual, expected)), (
            output, actual, expected
        )
        for word in page.get_text("words"):
            x0, y0, x1, y1 = word[:4]
            assert x0 >= -0.8 and y0 >= -0.8 and x1 <= page.rect.width + .8 and y1 <= page.rect.height + .8, (
                output, page.number, word
            )
    all_text = " ".join(p.get_text("text") for p in doc)
    # PDF extraction may insert line breaks after hyphens in narrow cells.
    # Ignore whitespace only: still require the complete worker identifier.
    assert expected_id in re.sub(r"\\s+", "", all_text), (output, expected_id, all_text[-350:])
    return len(doc)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    renderer = load_renderer()
    jobs = [
        ("form_6", 1, "SYN-EMP-0001"),
        ("form_34", 48, "SYN-EMP-0048"),
        ("form_38", 105, "SYN-EMP-0105"),
        ("form_9", 85, "SYN-EMP-0085"),
    ]
    for code, count, final in jobs:
        layout = form(code)
        rows = [
            {
                **{col["field_key"]: f"{i}" for col in layout["columns"]},
                "employee_name": f"SYN-EMP-{i:04}",
            }
            for i in range(1, count + 1)
        ]
        if code == "form_6":
            rows[0]["employee_name"] = final
        html = renderer(
            layout, rows, company_name="Synthetic Test Company",
            from_date="2026-10-01", to_date="2026-10-07", is_draft=True,
        )
        pdf_path = OUTPUT / f"{code}_a4.pdf"
        HTML(string=html, base_url=str(ROOT)).write_pdf(str(pdf_path))
        pages = check_pdf(pdf_path, layout["orientation"], final)
        print(f"A4 PDF PASS {code} {layout['orientation']} {pages} page(s), {count} entries")
    print("ALL_SYNTHETIC_A4_TESTS_PASSED")


if __name__ == "__main__":
    main()
