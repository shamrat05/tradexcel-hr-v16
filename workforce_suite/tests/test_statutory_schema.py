"""Behavior regressions for protected legal schema and shared export contracts."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from workforce_suite.workforce_suite.statutory_schema import validate_schema, reconcile_wages, missing_findings
from workforce_suite.workforce_suite.statutory_export_policy import available_languages
from workforce_suite.workforce_suite.statutory_print_html import render_html
from workforce_suite.workforce_suite.statutory_print_docx import render_docx

CAT = json.loads((Path(__file__).parents[1] / 'workforce_suite/statutory_form_specs.json').read_text())

@pytest.mark.parametrize('source', CAT['entries'], ids=lambda x:x['id'])
def test_each_catalog_schema_cannot_drop_duplicate_or_invent_source_fields(source):
    cols = deepcopy(source['columns'])
    assert validate_schema(source, cols)
    for bad in (cols[:-1], cols + [cols[0]], cols + [{'field_key': 'arbitrary_expression'}]):
        with pytest.raises(ValueError): validate_schema(source, bad)

def test_native_money_reconciliation_never_allocates_or_guesses():
    reconcile_wages(['100.10','20.20'], '120.30', '10.10', '110.20')
    reconcile_wages([120], 120, 10, 100, loan_repayment=10)
    with pytest.raises(ValueError, match='earnings'): reconcile_wages([100],120,10,110)
    with pytest.raises(ValueError, match='net'): reconcile_wages([120],120,10,109)

def test_missing_values_are_findings_but_zero_is_a_real_value():
    src={'columns':[{'field_key':'hours','label_en':'Approved hours'},{'field_key':'signature','label_en':'Signature','required_value':False}]}
    assert not missing_findings(src,[{'hours':0}])
    assert missing_findings(src,[{}])[0]['field']=='hours'
    assert missing_findings(src,[])[0]['code']=='NO_RECORDS'

def layout(code):
    row=deepcopy(next(x for x in CAT['entries'] if x['id']==code))
    return {**row,'form_code':code,'form_family':row['kind'],'title_en':row['ui_title'],'title_bn':'যাচাইকৃত খসড়া'}

def test_form81_preserves_all_source_sections_in_both_real_formats():
    doc=layout('form_81');sections={c['section_key'] for c in doc['columns']}
    assert len(sections)==12 and len(doc['columns'])>200
    rows=[{c['field_key']:'VALUE-'+c['field_key'] for c in doc['columns']}]
    for language in ('en','bn'):
        html=render_html(doc,rows,company_name='Synthetic',language=language)
        assert html.count('class="document-entry"')==12
        output=render_docx(doc,rows,company_name='Synthetic',language=language)
        with ZipFile(BytesIO(output)) as z:
            xml=z.read('word/document.xml').decode()
            assert all('VALUE-'+c['field_key'] in xml for c in doc['columns'])
            assert 'PAGE' in z.read('word/footer1.xml').decode()
            assert 'Noto Sans Bengali' in z.read('word/styles.xml').decode() if language=='bn' else True

def test_bangla_cannot_silently_use_english_notes():
    doc=layout('form_34');doc['header_note']='English heading'
    assert available_languages(doc)==('en',)
    doc['header_note_bn']='বাংলা শিরোনাম'
    assert available_languages(doc)==('en','bn')
    html=render_html(doc,[],company_name='Synthetic',language='bn')
    assert 'English heading' not in html

def test_leave_register_bulk_keeps_individual_worker_identity_and_source_columns():
    doc=layout('form_9');assert len(doc['columns'])==13
    html=render_html(doc,[{'employee':'A','employee_name':'SYN-A','worker_register_no':'REG-A','granted_days':1},
                          {'employee':'B','employee_name':'SYN-B','worker_register_no':'REG-B','granted_days':2}],company_name='Synthetic')
    assert html.count('<section class="leave-entry">')==2
    assert all(x in html for x in ('SYN-A','SYN-B','REG-A','REG-B'))


def test_docx_headings_use_black_and_native_bangla_font():
    from docx import Document
    from docx.shared import RGBColor
    doc=Document(BytesIO(render_docx(layout('form_81'),[],company_name='Synthetic',language='bn')))
    for name in ('Heading 1','Heading 2'):
        assert doc.styles[name].font.color.rgb==RGBColor(0,0,0)
        assert doc.styles[name].font.name=='Noto Sans Bengali'


def test_periodic_returns_require_complete_source_periods():
    from workforce_suite.workforce_suite.statutory_export_policy import normalize_period,period_mode
    assert period_mode('form_80','Manual')=='half-year'
    assert period_mode('form_81','Manual')=='year'
    assert normalize_period('form_80','Manual','2026-07-01','2026-12-31')==('2026-07-01','2026-12-31')
    assert normalize_period('form_81','Manual','2026-01-01','2026-12-31')==('2026-01-01','2026-12-31')
    for form in ('form_80','form_81'):
        with pytest.raises(ValueError):normalize_period(form,'Manual','2026-01-01','2026-01-31')


def test_docx_keeps_authorized_establishment_address():
    from docx import Document
    output=render_docx(layout('form_8'),[],company_name='Synthetic',company_address='TEST reviewed address')
    assert 'TEST reviewed address' in '\n'.join(p.text for p in Document(BytesIO(output)).paragraphs)


def test_contextual_export_respects_native_layout_visibility_before_rpc():
    import subprocess
    script=Path(__file__).parents[1]/'public/js/statutory_contextual_export.js'
    program="""const fs=require('fs'),vm=require('vm');let calls=0,messages=0;
    const context={window:{},__:(x)=>x,frappe:{model:{can_read:()=>false},
        msgprint:()=>messages++,call:()=>{calls++;throw Error('unexpected RPC')}}};
    vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context);
    context.window.workforceStatutoryExport('form_8',{company:'SYN'}).then(()=>{
        if(calls!==0||messages!==1)process.exit(1);
    });"""
    subprocess.run(['node','-e',program,str(script)],check=True)


def test_statutory_branding_uses_optional_native_logo_and_letterhead():
    from workforce_suite.workforce_suite.statutory_print_html import render_html

    doc = layout("form_8")
    html = render_html(
        doc, [], company_name="Synthetic",
        company_logo="/files/synthetic-logo.png",
        letter_head_content="<strong>Synthetic Establishment</strong>",
        letter_head_footer="Confidential footer",
    )
    assert 'src="/files/synthetic-logo.png"' in html
    assert "Synthetic Establishment" in html
    assert "Confidential footer" in html

    plain = render_html(doc, [], company_name="Synthetic")
    assert '<img class="company-logo"' not in plain
    assert "Confidential footer" not in plain


def test_form40_collection_date_is_required_only_for_actual_repayments():
    source = next(item for item in CAT["entries"] if item["id"] == "form_40")
    rows = [
        {"serial_no": 1, "_requital_required": False,
         "requital_amount": None, "requital_date": None},
        {"serial_no": 2, "_requital_required": True,
         "requital_amount": 100, "requital_date": None},
        {"serial_no": 3, "_requital_required": True,
         "requital_amount": 100, "requital_date": "2026-10-01"},
        # Without adapter proof that this is an unrepaid advance, fail closed.
        {"serial_no": 4, "requital_amount": 100, "requital_date": None},
    ]
    findings = missing_findings(source, rows)
    assert [item["row"] for item in findings
            if item.get("field") == "requital_date"] == [2, 4]


def test_form81_prescribed_numeric_cells_and_reconciliation_fail_closed():
    from workforce_suite.workforce_suite.statutory_structure import validate_evidence_values
    source = next(x for x in CAT['entries'] if x['id']=='form_81')
    validate_evidence_values(source, {'deductions_fine_cases':'0'})
    for value in ('missing', '-1', 'NaN', 'Infinity', '1.5'):
        with pytest.raises(ValueError):
            validate_evidence_values(source, {'deductions_fine_cases':value})
    with pytest.raises(ValueError, match='reconcile'):
        validate_evidence_values(source, {'deductions_fine_cases':'1','deductions_damage_cases':'2',
                                'deductions_absence_cases':'3','deductions_total_cases':'7'})
    assert {m['page'] for m in source['matrices']} >= {6,7,8,9,11}
    assert all(key in {c['field_key'] for c in source['columns']}
               for m in source['matrices'] for row in m['cells'] for key in row)


def test_variants_have_distinct_source_identity_and_prescribed_shift_cells():
    catalog={s['id']:s for s in CAT['entries']}
    consent={c['field_key'] for c in catalog['form_35']['columns']}
    withdrawal={c['field_key'] for c in catalog['form_35a']['columns']}
    assert 'consent_date' in consent and 'withdrawal_date' not in consent
    assert {'withdrawal_date','withdrawal_effective_date'} <= withdrawal
    assert 'consent_date' not in withdrawal
    for code,shifts in [('form_37',1),('form_37a',2),('form_37b',3)]:
        src=catalog[code]
        assert len(src['matrices'])==shifts
        assert all(len(m['cells'])==7 for m in src['matrices'])
        assert all(len(row)==(4 if shifts==3 else 3) for m in src['matrices'] for row in m['cells'])


def test_service_book_amended_history_is_repeatable_and_kept_in_both_formats():
    from workforce_suite.workforce_suite.statutory_structure import evidence_rows
    from types import SimpleNamespace
    class Cell(SimpleNamespace):
        def get(self,key):return getattr(self,key,None)
    src=layout('form_7')
    assert src['amendments'][0]['pages']==[22,23]
    entries=[Cell(field_key='wage_effective',field_value='2025-01-01',row_number=1),
             Cell(field_key='wage_basic',field_value='123',row_number=1),
             Cell(field_key='wage_effective',field_value='2026-01-01',row_number=2),
             Cell(field_key='wage_basic',field_value='456',row_number=2)]
    row=evidence_rows(entries,'form_7')
    assert [r['wage_basic'] for r in row['_history']['wage_history']]==['123','456']
    for language in ('en','bn'):
        html=render_html(src,[row],company_name='Synthetic',language=language)
        assert '2025-01-01' in html and '2026-01-01' in html
        from docx import Document
        doc=Document(BytesIO(render_docx(src,[row],company_name='Synthetic',language=language)))
        text=' '.join(cell.text for table in doc.tables for r in table.rows for cell in r.cells)
        assert all(x in text for x in ('2025-01-01','2026-01-01','123','456'))
    assert {t['id'] for t in src['repeatable_tables']}=={'employment_history','wage_history','leave_history','conduct_history'}


def test_form24_three_prescribed_parts_have_independent_repeatable_rows():
    src=next(s for s in CAT['entries'] if s['id']=='form_24')
    assert {t['id'] for t in src['repeatable_tables']}=={'test_certificate','equipment_exam','chain_exam'}
    assert len({key for t in src['repeatable_tables'] for key in t['keys']})==12


def test_word_embeds_supplied_native_logo_and_financial_evidence_is_not_payment_inference():
    import base64
    # Synthetic one-pixel PNG, independent of customer branding.
    png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a6y8AAAAASUVORK5CYII=')
    row={'_payment_rows':[{'worker':'TEST-W','state':'Payment Instructed','date':'2026-10-01','amount':123,'reference':'TEST-INSTRUCTION'}],
         '_rate_rows':[{'worker':'TEST-W','from':'2026-01-01','to':'2026-01-02','hours':2,'rate':10,'amount':20,'reference':'TEST-RATE'}]}
    for language in ('en','bn'):
        html=render_html(layout('form_38'),[row],company_name='Synthetic',language=language)
        assert 'TEST-INSTRUCTION' in html and 'TEST-RATE' in html
        output=render_docx(layout('form_38'),[row],company_name='Synthetic',language=language,company_logo_bytes=png)
        with ZipFile(BytesIO(output)) as z:
            assert any(name.startswith('word/media/') for name in z.namelist())
            assert 'TEST-INSTRUCTION' in z.read('word/document.xml').decode()


def test_appointment_source_pages_have_individual_terms_and_reconciled_wage_cells():
    src=layout('appointment_letter_sample')
    assert len(src['columns']) >= 40
    assert {1,2,3} == set(src['source_field_pages'].values())
    keys={c['field_key'] for c in src['columns']}
    assert {'spouse_name','national_id','present_address','permanent_address','overtime_terms',
            'resignation_notice','termination_notice','working_time_terms','leave_terms','increment_terms',
            'festival_bonus_terms','wage_payment_terms','grievance_terms','experience_terms',
            'establishment_rules','change_terms','governing_law_terms','wage_order_provenance'} <= keys
    from workforce_suite.workforce_suite.statutory_structure import validate_evidence_values
    values={'basic_wages':'100','contract_housing':'20','contract_transport':'5','contract_medical':'10',
            'contract_food':'0','contract_total':'135'}
    validate_evidence_values(src,values)
    with pytest.raises(ValueError,match='reconcile'):validate_evidence_values(src,{**values,'contract_total':'136'})
    values.update({key:'TEST-REVIEWED-'+key for key in keys-values.keys()})
    for language in ('en','bn'):
        html=render_html(src,[values],company_name='Synthetic',language=language)
        assert all('TEST-REVIEWED-'+key in html for key in ('resignation_notice','service_rule_availability','grievance_terms'))
        from docx import Document
        doc=Document(BytesIO(render_docx(src,[values],company_name='Synthetic',language=language)))
        text=' '.join(cell.text for table in doc.tables for row in table.rows for cell in row.cells)
        assert all('TEST-REVIEWED-'+key in text for key in ('resignation_notice','service_rule_availability','grievance_terms'))


def test_history_and_withdrawal_dates_preserve_source_chronology():
    from workforce_suite.workforce_suite.statutory_structure import validate_evidence_values, history_pages
    with pytest.raises(ValueError,match='chronology'):
        validate_evidence_values(layout('form_7'),{'history_joined':'2026-06-01','history_left':'2026-05-31'})
    with pytest.raises(ValueError,match='chronology'):
        validate_evidence_values(layout('form_35a'),{'withdrawal_date':'2026-10-09','withdrawal_effective_date':'2026-10-09'})
    with pytest.raises(ValueError,match='chronology'):
        validate_evidence_values(layout('form_35a'),{'withdrawal_date':'2026-10-09','withdrawal_effective_date':'2026-10-17'})
    validate_evidence_values(layout('form_35a'),{'withdrawal_date':'2026-10-09','withdrawal_effective_date':'2026-10-16'})
    pages=history_pages({'rows_per_page':6,'minimum_pages':4},[{'TEST':'REAL'}])
    assert len(pages)==4 and all(len(page)==6 for page in pages)
    assert pages[0][0]=={'TEST':'REAL'} and pages[0][1]=={} and pages[-1][-1]=={}
