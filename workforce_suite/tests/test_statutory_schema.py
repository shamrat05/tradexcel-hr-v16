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
    assert len(sections)==12 and len(doc['columns'])==105
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
