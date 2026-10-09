"""Real Frappe v16 synthetic statutory integration; run only on disposable sites."""
import os
from copy import deepcopy
from datetime import date
from pathlib import Path
from unittest.mock import patch

import frappe
import pytest

from workforce_suite.tests.persona_uat import SyntheticPersonaHarness
from workforce_suite.workforce_suite import statutory_forms as forms

@pytest.fixture(scope='module', autouse=True)
def site():
    target=os.environ.get('FRAPPE_TEST_SITE')
    assert target and os.environ.get('FRAPPE_TEST_SITES_PATH'), 'Explicit isolated statutory site required'
    frappe.init(site=target,sites_path=os.environ['FRAPPE_TEST_SITES_PATH'],force=True);frappe.connect()
    assert frappe.conf.workforce_rehearsal
    yield
    frappe.destroy()

@pytest.fixture
def data():
    frappe.set_user('Administrator');frappe.db.rollback()
    h=SyntheticPersonaHarness('STAT'+frappe.generate_hash(8).upper())
    reviewer=h.create_user('reviewer',['System Manager', 'Workforce Suite Manager'])
    auditor=h.create_user('auditor',['Workforce Compliance Auditor'],company='Example Company A')
    unscoped=h.create_user('unscoped',['Workforce Compliance Auditor'])
    worker=h.create_user('worker',['Workforce Employee/Worker'],company='Example Company A')
    person=h.create_employee('person','Example Company A',None,None)
    other=h.create_employee('other','Example Company B',None,None)
    holiday=frappe.get_doc({'doctype':'Holiday List','holiday_list_name':'TEST STAT '+frappe.generate_hash(8),
        'from_date':'2020-01-01','to_date':'2027-12-31','holidays':[]}).insert()
    holiday_assignments = []
    for employee in (person,other):
        company=frappe.db.get_value('Employee',employee,'company')
        assignment = frappe.get_doc({'doctype':'Holiday List Assignment','applicable_for':'Employee','assigned_to':employee,
            'employee_company':company,'holiday_list':holiday.name,'from_date':'2020-01-01'}).insert().submit()
        holiday_assignments.append(assignment.name)
    yield dict(h=h,reviewer=reviewer,auditor=auditor,unscoped=unscoped,worker=worker,person=person,other=other)
    frappe.set_user('Administrator');frappe.db.rollback()
    for name in holiday_assignments:
        if frappe.db.exists('Holiday List Assignment', name):
            assignment = frappe.get_doc('Holiday List Assignment', name)
            if assignment.docstatus == 1: assignment.cancel()
            frappe.delete_doc('Holiday List Assignment', name)
    if frappe.db.exists('Holiday List', holiday.name): frappe.delete_doc('Holiday List', holiday.name)
    frappe.db.commit();h.cleanup()
    assert not frappe.db.exists('Employee',person) and not frappe.db.exists('Employee',other)


def layout(code,company='Example Company A',**kwargs):
    source=forms.spec_for(code)
    doc=frappe.get_doc({'doctype':'Workforce Statutory Print Layout','title':'TEST STAT '+frappe.generate_hash(8),
        'company':company,'form_code':code,'form_family':source['kind'],'data_source':source['data_source'],
        'layout_style':'Minimal Black and White','orientation':source['orientation'],'template_version':'test-v1',
        'effective_from':'2020-01-01','title_en':source['ui_title'],'title_bn':'পরীক্ষামূলক রেজিস্টার',
        'columns':deepcopy(source['columns']),**kwargs})
    return doc.insert()


def profile(data):
    doc=frappe.get_doc({'doctype':'Workforce Statutory Profile','company':'Example Company A','profile_version':'test-1',
        'effective_from':'2020-01-01','establishment_en':'TEST Establishment','establishment_bn':'পরীক্ষামূলক প্রতিষ্ঠান',
        'address_en':'TEST Address','address_bn':'পরীক্ষামূলক ঠিকানা','legal_reference':'TEST reviewed source only',
        'review_notes':'TEST reviewed applicability',
        'registration_applicability':'Required','registration_no':'TEST-REG-001',
        'licence_applicability':'Not Applicable','licence_evidence':'TEST reviewed non-applicability evidence'}).insert()
    with pytest.raises(frappe.PermissionError):doc.submit()
    frappe.set_user(data['reviewer']);doc.reload();doc.submit();frappe.set_user('Administrator')
    return doc


def test_layout_protects_fields_components_versions_and_no_self_approval(data):
    doc=layout('form_8');doc.columns.pop()
    with pytest.raises(frappe.ValidationError,match='protected source'):doc.save()
    doc.reload();doc.columns[0].field_key='__import__'
    with pytest.raises(frappe.ValidationError):doc.save()
    doc.reload();doc.columns[0].required_value=0;doc.save();assert doc.columns[0].required_value==1
    with pytest.raises(frappe.PermissionError):doc.submit()
    frappe.set_user(data['reviewer']);doc.reload()
    with pytest.raises(frappe.ValidationError,match='legal'):doc.submit()


def test_native_scope_blocks_cross_company_employee_layout_and_unscoped_rest(data):
    first=layout('form_8');second=layout('form_8',company='Example Company B')
    frappe.set_user(data['auditor'])
    assert first.name in frappe.get_list(first.doctype,pluck='name')
    assert second.name not in frappe.get_list(first.doctype,pluck='name')
    with pytest.raises(frappe.PermissionError):forms.preview_a4(second.name,employee=data['other'])
    with pytest.raises(frappe.PermissionError):forms.preview_a4(first.name,employee=data['other'])
    frappe.set_user(data['unscoped']);assert not frappe.get_list(first.doctype,pluck='name')
    with pytest.raises(frappe.PermissionError):frappe.get_doc(first.doctype,first.name).check_permission('read')
    frappe.set_user(data['worker'])
    with pytest.raises(frappe.PermissionError):forms.preview_a4(first.name,employee=data['person'])


def test_employee_native_identity_missing_id_findings_and_evidence_cannot_override_money(data):
    doc=layout('form_8');preview=forms.preview_a4(doc.name,employee=data['person'])
    assert preview['row_count']==1
    assert any(f.get('field')=='worker_name_and_nid' for f in preview['findings'])
    assert data['person'] not in preview['html'] # Internal Employee ID is not statutory NID.
    record=frappe.get_doc({'doctype':'Workforce Statutory Record','company':doc.company,'layout':doc.name,
        'entry_date':'2020-01-01','employee':data['person'],'entries':[{'field_key':'gross_pay','field_value':'9999'}]})
    with pytest.raises(frappe.ValidationError,match='native-owned'):record.insert()
    record.entries[0].field_key='national_id';record.entries[0].field_value='TEST-NID';record.evidence_note='TEST reviewed HR identity source';record.insert()
    with pytest.raises(frappe.PermissionError):record.submit()
    frappe.set_user(data['reviewer']);record.reload();record.submit();frappe.set_user('Administrator')
    preview=forms.preview_a4(doc.name,employee=data['person'])
    assert 'TEST-NID' in preview['html']
    assert not any(f.get('field')=='worker_name_and_nid' for f in preview['findings'])


def test_profile_four_eyes_effective_dates_and_bn_no_fallback(data):
    approved=profile(data);doc=layout('form_8',statutory_profile=approved.name)
    result=forms.preview_a4(doc.name,employee=data['person'],language='bn')
    assert 'পরীক্ষামূলক প্রতিষ্ঠান' in result['html'] and 'TEST Establishment' not in result['html']
    approved_copy=frappe.get_doc({'doctype':'Workforce Statutory Profile','company':'Example Company B','profile_version':'1','effective_from':'2020-01-01','establishment_en':'TEST','address_en':'TEST','legal_reference':'TEST','review_notes':'TEST',
        'registration_applicability':'Required','registration_no':'TEST-REG-002',
        'licence_applicability':'Not Applicable','licence_evidence':'TEST evidence'}).insert()
    doc.statutory_profile=approved_copy.name
    with pytest.raises(frappe.ValidationError,match='match'):doc.save()


def test_submitted_attendance_weekly_hours_not_raw_checkins_or_draft(data):
    person=data['person'];doc=layout('form_34')
    att=frappe.get_doc({'doctype':'Attendance','employee':person,'company':doc.company,'attendance_date':'2026-10-02','status':'Present','working_hours':7}).insert()
    assert forms._read_attendance(doc,'2026-10-02','2026-10-08',(person,))==[]
    att.submit();rows=forms._read_attendance(doc,'2026-10-02','2026-10-08',(person,))
    assert rows[0]['day_fri']==7 and rows[0]['total_work_hours']==7
    assert 'approved_overtime_hours' not in rows[0] # No invented overtime from working_hours.
    with pytest.raises(frappe.ValidationError,match='Friday'):forms.preview_a4(doc.name,'2026-10-01','2026-10-31',employee=person)


def test_manual_return_review_not_official_and_form81_full_section_export(data):
    doc=layout('form_81');entry=frappe.get_doc({'doctype':'Workforce Statutory Record','company':doc.company,'layout':doc.name,
        'entry_date':'2026-10-02','reporting_from':'2026-01-01','reporting_to':'2026-12-31',
        'entries':[{'field_key':c.field_key,'field_value':'0' if c.field_key in forms.spec_for('form_81').get('value_types',{}) and forms.spec_for('form_81')['value_types'][c.field_key]!='text' else 'TEST '+c.field_key,'value_status':'Evidence Entered'} for c in doc.columns],
        'evidence_note':'TEST reviewed establishment return evidence'}).insert()
    assert forms.preview_a4(doc.name,'2026-01-01','2026-12-31')['row_count']==0 # Draft evidence is not approved evidence.
    frappe.set_user(data['reviewer']);entry.reload();entry.submit();frappe.set_user('Administrator')
    preview=forms.preview_a4(doc.name,'2026-01-01','2026-12-31')
    assert preview['row_count']==1 and preview['html'].count('class="document-entry"')==12
    assert preview['status']=='Draft'


def test_docx_generation_audit_is_immutable_and_does_not_claim_payment_or_filing(data):
    doc=layout('form_8');forms.download_docx(doc.name,employee=data['person'])
    assert frappe.local.response.filecontent[:2]==b'PK'
    audit=frappe.get_last_doc('Workforce Statutory Export')
    assert audit.status=='Draft Generated' and audit.template_version=='test-v1'
    assert audit.generated_by=='Administrator' and len(audit.payload_sha256)==64
    assert 'TEST PERSONA' not in audit.scope_json and 'national_id' not in audit.scope_json
    audit.template_version='forged'
    with pytest.raises(frappe.ValidationError,match='immutable'):audit.save(ignore_permissions=True)
    with pytest.raises(frappe.ValidationError):frappe.delete_doc(audit.doctype,audit.name,ignore_permissions=True)
    forged=frappe.get_doc({**audit.as_dict(),'name':None})
    with pytest.raises(frappe.PermissionError):forged.insert(ignore_permissions=True)


def test_cancelled_expired_or_partial_period_layout_fails_closed(data):
    doc=layout('form_34',effective_from='2026-10-03')
    with pytest.raises(frappe.ValidationError,match='effective'):forms.preview_a4(doc.name,'2026-10-02','2026-10-08',employee=data['person'])
    doc=layout('form_8');doc.db_set('docstatus',2)
    with pytest.raises(frappe.ValidationError,match='Cancelled'):forms.preview_a4(doc.name,employee=data['person'])


def test_native_leave_ledger_balances_and_clipped_approved_history(data):
    from workforce_suite.workforce_suite.statutory_native_data import leave_balances
    from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on
    token=frappe.generate_hash(8)
    types=[]
    for category in ('annual','casual','sick'):
        leave=frappe.get_doc({'doctype':'Leave Type','leave_type_name':'TEST STAT '+category+' '+token,'max_leaves_allowed':30}).insert()
        allocation=frappe.get_doc({'doctype':'Leave Allocation','employee':data['person'],'company':'Example Company A',
            'leave_type':leave.name,'from_date':'2026-01-01','to_date':'2026-12-31','new_leaves_allocated':12}).insert()
        allocation.submit();types.append(leave.name)
    approved=profile(data)
    # Create a separately reviewed version with explicit native Leave Type mappings.
    copy=frappe.copy_doc(approved);copy.docstatus=0;copy.profile_version='test-2';copy.annual_leave_type,copy.casual_leave_type,copy.sick_leave_type=types;copy.insert()
    frappe.set_user(data['reviewer']);copy.submit();frappe.set_user('Administrator')
    doc=layout('form_9',statutory_profile=copy.name)
    application=frappe.get_doc({'doctype':'Leave Application','employee':data['person'],'company':doc.company,
        'leave_type':types[0],'from_date':'2026-10-01','to_date':'2026-10-03','status':'Approved','leave_approver':data['reviewer']}).insert()
    assert forms._read_leave(doc,'2026-10-02','2026-10-31',(data['person'],))==[]
    application.submit()
    balances,findings=leave_balances(doc,(data['person'],),'2026-10-02','2026-10-31')
    assert not findings
    assert balances[data['person']]['annual_balance']==get_leave_balance_on(data['person'],types[0],'2026-10-31',to_date='2026-10-31')
    rows=forms._read_leave(doc,'2026-10-02','2026-10-31',(data['person'],))
    assert rows[0]['granted_days']==2 and rows[0]['_leave_application']==application.name
    assert 'grant_date' not in rows[0] # modified timestamp is not a legal decision date.


def test_native_salary_slip_mapping_reconciles_multiple_components_and_excludes_draft(data):
    from workforce_suite.tests.test_payroll_finalization_integration import _component,_create_structure,_create_assignment
    from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip
    company='Example Company A';token=frappe.generate_hash(7)
    expense=frappe.db.get_value('Account',{'company':company,'root_type':'Expense','is_group':0},'name')
    basic=_component('TEST STAT Base '+token,'SB'+token[:3],company,expense)
    second=_component('TEST STAT Base Supplement '+token,'SC'+token[:3],company,expense)
    structure=_create_structure('TEST STAT Structure '+token,company,'BDT','Monthly Salary',basic.name,100)
    # Native structure remains authoritative; a new version holds two earnings.
    structure.cancel();structure=frappe.copy_doc(structure);structure.name='TEST STAT Structure 2 '+token;structure.docstatus=0
    structure.append('earnings',{'salary_component':second.name,'amount':25,'depends_on_payment_days':0});structure.insert();structure.submit()
    payable=frappe.db.get_value('Company',company,'default_payroll_payable_account')
    center=frappe.db.get_value('Company',company,'cost_center')
    _create_assignment(data['person'],company,'BDT',payable,structure.name,125,center,from_date='2026-01-01')
    doc=layout('form_38',salary_mappings=[{'field_key':'basic_wage','salary_component':basic.name},{'field_key':'basic_wage','salary_component':second.name}])
    slip=make_salary_slip(structure.name,employee=data['person'],posting_date='2026-09-30')
    slip.start_date='2026-09-01';slip.end_date='2026-09-30';slip.payroll_frequency='Monthly';slip.insert()
    assert forms._read_salary_slips(doc,'2026-09-01','2026-09-30',(data['person'],))==[]
    slip.submit()
    rows=forms._read_salary_slips(doc,'2026-09-01','2026-09-30',(data['person'],))
    assert len(rows)==1 and rows[0]['basic_wage']==slip.gross_pay and rows[0]['net_pay']==slip.net_pay
    assert 'worker_signature' not in rows[0] and rows[0]['_payment_status']!='PAID'
    from workforce_suite.workforce_suite.statutory_financial_evidence import apply_financial_evidence
    from frappe.utils.file_manager import save_file
    file=save_file('TEST-receipt-'+token+'.txt',b'TEST synthetic payment evidence',None,None,is_private=1)
    owned_path=Path(file.get_full_path())
    try:
        receipt=frappe.get_doc({'doctype':'Workforce Statutory Record','company':company,'layout':doc.name,
            'employee':data['person'],'entry_date':'2026-10-01','evidence_kind':'Worker Payment Evidenced',
            'reference_doctype':'Salary Slip','reference_name':slip.name,'payment_date':'2026-09-30',
            'payment_amount':slip.net_pay,'payment_reference':'TEST-RECEIPT-'+token,
            'evidence_file':file.file_url,'evidence_note':'TEST private original payment receipt'}).insert()
        with pytest.raises(frappe.PermissionError):receipt.submit()
        frappe.set_user(data['reviewer']);receipt.reload();receipt.submit();frappe.set_user('Administrator')
        evidenced=apply_financial_evidence(doc,rows[0],'2026-09-01','2026-09-30')
        assert evidenced['_worker_payment_status']=='Fully Evidenced'
        assert evidenced['_financial_evidence']==[receipt.name]
        assert evidenced['_payment_status']!='PAID'
    finally:
        owned_path.unlink(missing_ok=True)
    with pytest.raises(frappe.ValidationError,match='cuts'):forms._read_salary_slips(doc,'2026-09-02','2026-09-30',(data['person'],))
    doc.salary_mappings.pop();doc.save()
    with pytest.raises(frappe.ValidationError,match='Map every'):forms._read_salary_slips(doc,'2026-09-01','2026-09-30',(data['person'],))
    doc.append('salary_mappings',{'field_key':'other_pay','salary_component':basic.name})
    with pytest.raises(frappe.ValidationError,match='two wage'):doc.save()


def test_private_evidence_file_cannot_be_public_and_branch_scope_cannot_broaden(data):
    doc=layout('form_8')
    file=frappe.get_doc({'doctype':'File','file_name':'synthetic-stat.txt','file_url':'https://example.test/synthetic','is_private':0}).insert()
    evidence=frappe.get_doc({'doctype':'Workforce Statutory Record','company':doc.company,'layout':doc.name,
        'entry_date':'2020-01-01','employee':data['person'],'evidence_file':file.file_url,'entries':[{'field_key':'card_no','field_value':'TEST'}]})
    with pytest.raises(frappe.PermissionError,match='private'):evidence.insert()
    with pytest.raises(frappe.ValidationError,match='Branch'):forms.preview_a4(doc.name,employee=data['person'],branch='Nonexistent Branch')


def test_approved_native_overtime_uses_additional_salary_not_inferred_work_hours(data):
    from workforce_suite.tests.test_payroll_finalization_integration import _component,_create_structure,_create_assignment
    from workforce_suite.workforce_suite.statutory_native_data import approved_overtime
    token=frappe.generate_hash(7);company='Example Company A'
    account=frappe.db.get_value('Account',{'company':company,'root_type':'Expense','is_group':0},'name')
    base=_component('TEST STAT OT Base '+token,'OB'+token[:3],company,account)
    overtime=_component('TEST STAT OT '+token,'OT'+token[:3],company,account)
    structure=_create_structure('TEST STAT OT Structure '+token,company,'BDT','Monthly Salary',base.name,100)
    _create_assignment(data['person'],company,'BDT',frappe.db.get_value('Company',company,'default_payroll_payable_account'),
        structure.name,100,frappe.db.get_value('Company',company,'cost_center'),from_date='2026-01-01')
    ot_type=frappe.get_doc({'doctype':'Overtime Type','name':'TEST STAT OT '+token,
        'overtime_salary_component':overtime.name,'overtime_calculation_method':'Fixed Hourly Rate',
        'hourly_rate':15,'standard_multiplier':1,'maximum_overtime_hours_allowed':2}).insert()
    attendance=frappe.get_doc({'doctype':'Attendance','employee':data['person'],'company':company,
        'attendance_date':'2026-10-02','status':'Present','working_hours':10,'standard_working_hours':8,
        'actual_overtime_duration':2,'overtime_type':ot_type.name}).insert();attendance.submit()
    # Controlled finalized-period fixture, with the same native snapshot contract
    # used by payroll integration tests; reporting never finalizes Attendance.
    from workforce_suite.workforce_suite.attendance_payroll_boundary import current_attendance_period_hash
    period=frappe.get_doc({'doctype':'Workforce Attendance Period','company':company,
        'from_date':'2026-10-02','to_date':'2026-10-08','status':'Finalized','revision':1,
        'attendance_hash':current_attendance_period_hash(company,'2026-10-02','2026-10-08')})
    period._finalize_context=True;period.insert()
    doc=layout('form_34')
    assert not approved_overtime(doc,(data['person'],),'2026-10-02','2026-10-08')[0]
    slip=frappe.get_doc({'doctype':'Overtime Slip','employee':data['person'],'company':company,
        'start_date':'2026-10-02','end_date':'2026-10-08','posting_date':'2026-10-08',
        'overtime_details':[{'date':'2026-10-02','reference_document':attendance.name,
            'overtime_type':ot_type.name,'overtime_duration':2,'standard_working_hours':8}]}).insert()
    assert not approved_overtime(doc,(data['person'],),'2026-10-02','2026-10-08')[0]
    slip.submit()
    amount=frappe.db.get_value('Additional Salary',{'ref_doctype':'Overtime Slip','ref_docname':slip.name,'docstatus':1},'amount')
    native,findings=approved_overtime(doc,(data['person'],),'2026-10-02','2026-10-08')
    assert native[data['person']]['hours']==2 and native[data['person']]['amount']==amount==30
    rows=forms._read_attendance(doc,'2026-10-02','2026-10-08',(data['person'],))
    assert rows[0]['total_work_hours']==10 and rows[0]['approved_overtime_hours']==2 and rows[0]['overtime_pay']==30
    assert 'overtime_hourly_rate' not in rows[0] and any(f['code']=='OVERTIME_RATE_EVIDENCE' for f in findings)
    assert not approved_overtime(doc,(data['other'],),'2026-10-02','2026-10-08')[0]
    partial,findings=approved_overtime(doc,(data['person'],),'2026-10-02','2026-10-02')
    assert not partial[data['person']]['complete'] and any(f['code']=='OVERTIME_PERIOD' for f in findings)


def test_personal_pdf_filename_uses_normalized_context_not_ignored_caller_dates(data):
    doc=layout('form_8')
    with patch('frappe.utils.pdf.get_pdf',return_value=b'%PDF-TEST-CONVERTER-STUB'):
        forms.download_a4(doc.name,from_date='../ignored',to_date='ignored',employee=data['person'])
    assert frappe.local.response.filename=='form_8_en_employee_document.pdf'


@pytest.mark.parametrize("narrowing", ["Employee", "Department", "Branch"])
@pytest.mark.parametrize("actor", ["auditor", "reviewer"])
def test_narrowed_operator_cannot_read_whole_establishment_manual_evidence(data, narrowing, actor):
    doc=layout('form_81')
    record=frappe.get_doc({'doctype':'Workforce Statutory Record','company':doc.company,'layout':doc.name,
        'entry_date':'2026-01-01','reporting_from':'2026-01-01','reporting_to':'2026-12-31','evidence_note':'TEST establishment-wide sensitive evidence',
        'entries':[{'field_key':c.field_key,'field_value':('TEST-MANUAL-RESTRICTED' if c.field_key=='licence_no' else ('0' if forms.spec_for('form_81').get('value_types',{}).get(c.field_key) in ('integer','decimal','signed_decimal') else 'TEST evidence')), 'value_status':'Evidence Entered'} for c in doc.columns]}).insert()
    frappe.set_user(data['reviewer']);record.submit();frappe.set_user('Administrator')
    target=data['person'] if narrowing=='Employee' else frappe.db.get_value(narrowing,{'company':doc.company},'name')
    assert target
    permission=frappe.get_doc({'doctype':'User Permission','user':data[actor],'allow':narrowing,
        'for_value':target,'apply_to_all_doctypes':1}).insert()
    data['h'].permissions.append(permission.name);frappe.clear_cache(user=data[actor])
    frappe.set_user(data[actor])
    assert record.name not in frappe.get_list('Workforce Statutory Record',pluck='name')
    with pytest.raises(frappe.PermissionError):record.check_permission('read')
    with pytest.raises(frappe.PermissionError):forms.preview_a4(doc.name,'2026-01-01','2026-12-31')


def test_branch_scoped_auditor_can_read_matching_manual_establishment(data):
    branch=frappe.db.get_value('Branch',{'company':'Example Company A'},'name');assert branch
    doc=layout('form_81',branch=branch)
    record=frappe.get_doc({'doctype':'Workforce Statutory Record','company':doc.company,'branch':branch,'layout':doc.name,
        'entry_date':'2026-01-01','reporting_from':'2026-01-01','reporting_to':'2026-12-31','evidence_note':'TEST reviewed establishment evidence',
        'entries':[{'field_key':c.field_key,'field_value':('TEST-MATCHING-BRANCH' if c.field_key=='licence_no' else ('0' if forms.spec_for('form_81').get('value_types',{}).get(c.field_key) in ('integer','decimal','signed_decimal') else 'TEST evidence')), 'value_status':'Evidence Entered'} for c in doc.columns]}).insert()
    frappe.set_user(data['reviewer']);record.submit();frappe.set_user('Administrator')
    permission=frappe.get_doc({'doctype':'User Permission','user':data['auditor'],'allow':'Branch',
        'for_value':branch,'apply_to_all_doctypes':1}).insert();data['h'].permissions.append(permission.name)
    frappe.clear_cache(user=data['auditor']);frappe.set_user(data['auditor'])
    assert record.name in frappe.get_list('Workforce Statutory Record',pluck='name')
    record.check_permission('read')
    assert forms.preview_a4(doc.name,'2026-01-01','2026-12-31')['row_count']==1


def test_explicit_draft_setup_is_repeatable_preserves_edits_and_never_approves(data):
    from workforce_suite.workforce_suite.statutory_setup import prepare_draft_layout
    branch = frappe.get_doc({'doctype':'Branch','branch':'TEST SETUP '+frappe.generate_hash(8),
                             'company':'Example Company A'}).insert()
    frappe.db.commit()
    names = []
    try:
        first = prepare_draft_layout('Example Company A', 'form_8', '2026-10-01', branch.name)
        names = list(first['layouts']); assert first['created'] and len(names) == 1
        doc = frappe.get_doc('Workforce Statutory Print Layout', names[0])
        assert doc.docstatus == 0 and not doc.statutory_profile and not doc.approved_by
        assert not doc.title_bn and not doc.salary_mappings
        doc.title = 'TEST administrator draft edit'; doc.columns[0].label_en = 'TEST custom label'; doc.save()
        frappe.db.commit()
        again = prepare_draft_layout('Example Company A', 'form_8', '2027-01-01', branch.name)
        assert again == {'created': False, 'layouts': names}
        doc.reload(); assert doc.title == 'TEST administrator draft edit'
        assert doc.columns[0].label_en == 'TEST custom label' and str(doc.effective_from) == '2026-10-01'
        assert len(frappe.get_all(doc.doctype, filters={'company':doc.company,'branch':branch.name})) == 1
        with pytest.raises(frappe.ValidationError):
            prepare_draft_layout('Example Company B', 'form_8', '2026-10-01', branch.name)
        external = prepare_draft_layout('Example Company A', 'form_32', '2026-10-01', branch.name)
        names.extend(external['layouts'])
        certificate_layout=frappe.get_doc('Workforce Statutory Print Layout', external['layouts'][0])
        assert certificate_layout.form_family=='Evidence Only'
        with pytest.raises(frappe.ValidationError, match='externally issued'):
            forms.preview_a4(certificate_layout.name, '2026-10-01', '2026-10-31')
        with pytest.raises(frappe.ValidationError):
            prepare_draft_layout('Example Company A', 'form_8', '', branch.name)
        frappe.set_user(data['auditor'])
        with pytest.raises(frappe.PermissionError):
            prepare_draft_layout('Example Company B', 'form_8', '2026-10-01')
        frappe.set_user(data['worker'])
        with pytest.raises(frappe.PermissionError):
            prepare_draft_layout('Example Company A', 'form_8', '2026-10-01')
    finally:
        frappe.set_user('Administrator'); frappe.db.rollback()
        for name in names:
            if frappe.db.exists('Workforce Statutory Print Layout', name):
                frappe.delete_doc('Workforce Statutory Print Layout', name)
        frappe.delete_doc('Branch', branch.name); frappe.db.commit()
        assert all(not frappe.db.exists('Workforce Statutory Print Layout', n) for n in names)


def test_draft_profile_setup_reuses_company_and_reports_review_gaps(data):
    from workforce_suite.workforce_suite.statutory_setup import (
        prepare_draft_profile, prepare_draft_layout, profile_missing_requirements,
    )
    first = prepare_draft_profile("Example Company A", effective_from="2026-10-01")
    assert first["created"] and len(first["profiles"]) == 1
    profile_name = first["profiles"][0]
    profile_doc = frappe.get_doc("Workforce Statutory Profile", profile_name)
    assert profile_doc.docstatus == 0
    assert profile_doc.establishment_en == "Example Company A"
    assert any(item["field"] in {"registration_no", "legal_reference", "docstatus"} for item in first["missing_requirements"])
    again = prepare_draft_profile("Example Company A", effective_from="2027-01-01")
    assert again["created"] is False and again["profiles"] == [profile_name]
    layout_result = prepare_draft_layout("Example Company A", "form_8", "2026-10-01")
    layout_doc = frappe.get_doc("Workforce Statutory Print Layout", layout_result["layouts"][0])
    assert not layout_doc.statutory_profile
    assert profile_missing_requirements(profile_name)
    frappe.delete_doc("Workforce Statutory Print Layout", layout_doc.name)
    frappe.delete_doc("Workforce Statutory Profile", profile_name)
    frappe.db.commit()

def test_profile_requirements_enforce_read_scope_and_submission_completeness(data):
    from workforce_suite.workforce_suite.statutory_setup import prepare_draft_profile, profile_missing_requirements
    first = prepare_draft_profile("Example Company A", effective_from="2026-10-01")
    name = first["profiles"][0]
    try:
        assert profile_missing_requirements(name)
        frappe.set_user(data["worker"])
        with pytest.raises(frappe.PermissionError):
            profile_missing_requirements(name)
        frappe.set_user(data["auditor"])
        assert profile_missing_requirements(name)
        frappe.set_user(data["unscoped"])
        with pytest.raises(frappe.PermissionError):
            profile_missing_requirements(name)
        frappe.set_user(data["reviewer"])
        doc = frappe.get_doc("Workforce Statutory Profile", name)
        with pytest.raises(frappe.ValidationError, match="Complete reviewed statutory fields"):
            doc.submit()
    finally:
        frappe.set_user("Administrator")
        if frappe.db.exists("Workforce Statutory Profile", name):
            frappe.delete_doc("Workforce Statutory Profile", name)
        frappe.db.commit()


def test_draft_setup_concurrent_blank_branch_requests_create_one_configuration():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from workforce_suite.workforce_suite.statutory_setup import prepare_draft_layout
    frappe.set_user('Administrator'); frappe.db.rollback()
    scope = {'company':'Example Company A','form_code':'form_19','branch':['is','not set']}
    assert not frappe.get_all('Workforce Statutory Print Layout', filters=scope), 'Isolated setup scope must be empty'
    barrier = Barrier(2); names = []
    def request(branch):
        frappe.init(site=os.environ['FRAPPE_TEST_SITE'], sites_path=os.environ['FRAPPE_TEST_SITES_PATH'])
        frappe.connect(); frappe.set_user('Administrator')
        try:
            # Establish a pre-insert transaction snapshot in both requests.
            # The action's locking current read must still see the winner.
            frappe.get_all('Workforce Statutory Print Layout', filters=scope)
            barrier.wait(timeout=10)
            return prepare_draft_layout('Example Company A', 'form_19', '2026-10-01', branch)
        finally:
            frappe.db.rollback(); frappe.destroy()
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(request, value) for value in (None, '')]
            results = [future.result(timeout=60) for future in futures]
        names = sorted({name for result in results for name in result['layouts']})
        assert len(names) == 1 and sum(result['created'] for result in results) == 1
        frappe.db.rollback()  # Observe committed worker results in a new snapshot.
        assert len(frappe.get_all('Workforce Statutory Print Layout', filters=scope)) == 1
    finally:
        frappe.db.rollback()
        # Only this test's initially empty, explicit synthetic scope is owned.
        for row in frappe.get_all('Workforce Statutory Print Layout', filters=scope):
            frappe.delete_doc('Workforce Statutory Print Layout', row.name)
        frappe.db.commit()
        assert not frappe.get_all('Workforce Statutory Print Layout', filters=scope)


def test_profile_applicability_requires_reviewed_required_or_evidenced_not_applicable(data):
    frappe.set_user("Administrator")
    doc = frappe.get_doc({
        "doctype": "Workforce Statutory Profile",
        "company": "Example Company A",
        "profile_version": "test-applicability",
        "effective_from": "2026-10-01",
        "establishment_en": "TEST Establishment",
        "establishment_bn": "পরীক্ষামূলক প্রতিষ্ঠান",
        "address_en": "TEST Address",
        "address_bn": "পরীক্ষামূলক ঠিকানা",
        "legal_reference": "TEST reviewed law",
        "review_notes": "TEST reviewed applicability",
        "registration_applicability": "Pending Review",
        "licence_applicability": "Pending Review",
    }).insert()
    try:
        frappe.set_user(data["reviewer"])
        with pytest.raises(frappe.ValidationError, match="applicability review"):
            doc.submit()
        doc.reload()
        doc.registration_applicability = "Required"
        doc.registration_no = "TEST-REG-001"
        doc.licence_applicability = "Not Applicable"
        doc.licence_evidence = "TEST evidence: licence not applicable for this establishment"
        doc.submit()
        assert doc.docstatus == 1
    finally:
        frappe.set_user("Administrator")
        if frappe.db.exists("Workforce Statutory Profile", doc.name):
            current = frappe.get_doc("Workforce Statutory Profile", doc.name)
            if current.docstatus == 1:
                current.cancel()
            frappe.delete_doc("Workforce Statutory Profile", doc.name)
        frappe.db.commit()


def test_concurrent_draft_profile_requests_create_one_profile_and_keep_scope(data):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from workforce_suite.workforce_suite.statutory_setup import prepare_draft_profile
    frappe.set_user("Administrator")
    scope = {"company": "Example Company A", "branch": ["is", "not set"]}
    assert not frappe.get_all("Workforce Statutory Profile", filters=scope)
    barrier = Barrier(2)
    def request():
        frappe.init(site=os.environ["FRAPPE_TEST_SITE"], sites_path=os.environ["FRAPPE_TEST_SITES_PATH"])
        frappe.connect()
        frappe.set_user("Administrator")
        try:
            frappe.get_all("Workforce Statutory Profile", filters=scope)
            barrier.wait(timeout=10)
            return prepare_draft_profile("Example Company A", effective_from="2026-10-01")
        finally:
            frappe.db.rollback()
            frappe.destroy()
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [future.result(timeout=60) for future in [pool.submit(request), pool.submit(request)]]
        names = sorted({name for result in results for name in result["profiles"]})
        assert len(names) == 1
        assert sum(result["created"] for result in results) == 1
    finally:
        frappe.set_user("Administrator")
        frappe.db.rollback()
        for row in frappe.get_all("Workforce Statutory Profile", filters=scope):
            frappe.delete_doc("Workforce Statutory Profile", row.name)
        frappe.db.commit()


def test_form40_requitals_are_repeatable_and_render_as_separate_rows(data):
    from workforce_suite.workforce_suite.statutory_forms import _read_manual, _print_context
    doc = layout("form_40")
    record = frappe.get_doc({
        "doctype": "Workforce Statutory Record",
        "company": doc.company,
        "layout": doc.name,
        "entry_date": "2026-10-02",
        "evidence_note": "TEST reviewed advance evidence",
        "entries": [
            {"field_key": "worker_register_no", "field_value": "TEST-REG-40"},
            {"field_key": "employee_name", "field_value": "TEST Worker"},
            {"field_key": "advance_amount_date", "field_value": "1000 BDT / 2026-09-01"},
            {"field_key": "remarks", "field_value": "TEST advance note"},
        ],
        "requitals": [
            {"amount": 250, "collection_date": "2026-09-30", "reference": "TEST-R1"},
            {"amount": 250, "collection_date": "2026-10-01", "reference": "TEST-R2", "remarks": "TEST installment note"},
        ],
    }).insert()
    empty_record = frappe.get_doc({
        "doctype": "Workforce Statutory Record",
        "company": doc.company,
        "layout": doc.name,
        "entry_date": "2026-10-03",
        "evidence_note": "TEST advance awaiting first repayment",
        "entries": [
            {"field_key": "worker_register_no", "field_value": "TEST-REG-41"},
            {"field_key": "employee_name", "field_value": "TEST Worker 2"},
            {"field_key": "advance_amount_date", "field_value": "500 BDT / 2026-09-15"},
            {"field_key": "remarks", "field_value": "TEST unrepaid advance"},
        ],
    }).insert()
    try:
        frappe.set_user(data["reviewer"])
        record.submit()
        empty_record.submit()
        rows = _read_manual(doc, "2026-10-01", "2026-10-31")
        assert len(rows) == 3
        assert [row["requital_amount"] for row in rows[:2]] == [250, 250]
        assert [str(row["requital_date"]) for row in rows[:2]] == ["2026-09-30", "2026-10-01"]
        assert rows[0]["remarks"] == "TEST advance note / TEST-R1"
        assert rows[1]["remarks"] == "TEST advance note / TEST-R2 / TEST installment note"
        assert rows[2]["requital_amount"] is None
        assert rows[2]["requital_date"] is None
        assert rows[2]["remarks"] == "TEST unrepaid advance"
        _, _, preview_data = _print_context(doc.name, "2026-10-01", "2026-10-31")
        assert not any(
            finding.get("field") == "requital_date"
            for finding in preview_data["findings"]
        )
        # Exercise the final preview gate too: an actual repayment with a
        # missing date must retain its finding, unlike the unrepaid advance.
        incomplete_rows = deepcopy(rows)
        incomplete_rows[0]["requital_date"] = None
        with patch.object(forms, "_source_rows", return_value=incomplete_rows):
            _, _, incomplete_preview = _print_context(
                doc.name, "2026-10-01", "2026-10-31"
            )
        assert [
            finding["row"] for finding in incomplete_preview["findings"]
            if finding.get("field") == "requital_date"
        ] == [1]
    finally:
        frappe.set_user("Administrator")
        for item in (record, empty_record):
            if frappe.db.exists(item.doctype, item.name):
                current = frappe.get_doc(item.doctype, item.name)
                if current.docstatus == 1:
                    current.cancel()
                # Queue cleanup is intentionally avoided here: this isolated
                # regression must remain runnable when the bench queue is full.
                frappe.db.delete("Workforce Statutory Requital", {"parent": item.name})
                frappe.db.delete("Workforce Statutory Value", {"parent": item.name})
                frappe.db.delete(item.doctype, {"name": item.name})
        frappe.db.delete(doc.doctype, {"name": doc.name})
        frappe.db.commit()


def test_periodic_return_aggregation_uses_submitted_attendance_and_fails_closed(monkeypatch):
    from types import SimpleNamespace
    from workforce_suite.workforce_suite import statutory_native_data as native

    employees = [
        SimpleNamespace(name="TEST-E-M", gender="Male", date_of_birth="1990-01-01"),
        SimpleNamespace(name="TEST-E-F", gender="Female", date_of_birth="1992-01-01"),
    ]
    attendance = [
        SimpleNamespace(employee="TEST-E-M", attendance_date="2026-01-01", status="Present"),
        SimpleNamespace(employee="TEST-E-F", attendance_date="2026-01-01", status="Present"),
        SimpleNamespace(employee="TEST-E-M", attendance_date="2026-01-02", status="Present"),
    ]

    class FakeFrappe:
        @staticmethod
        def has_permission(doctype, *args):
            return True
        @staticmethod
        def get_list(doctype, **kwargs):
            return employees if doctype == "Employee" else attendance

    monkeypatch.setattr(native, "frappe", FakeFrappe)
    layout = type("Layout", (), {"form_code": "form_80", "company": "Synthetic", "branch": ""})()
    rows = native.aggregate_periodic_return(layout, "2026-01-01", "2026-06-30")
    assert rows[0]["adult_male"] == 1.0
    assert rows[0]["adult_female"] == 0.5
    assert any(item["code"] == "WORKING_DAYS_REVIEW" for item in rows[0]["_findings"])

    class NoAttendance(FakeFrappe):
        @staticmethod
        def get_list(doctype, **kwargs):
            return employees if doctype == "Employee" else []

    monkeypatch.setattr(native, "frappe", NoAttendance)
    empty = native.aggregate_periodic_return(layout, "2026-01-01", "2026-06-30")
    assert "adult_male" not in empty[0]
    assert any(item["code"] == "ATTENDANCE_OBSERVATIONS_MISSING"
               for item in empty[0]["_findings"])


def test_periodic_historical_selection_scope_duplicates_and_partial_coverage(monkeypatch):
    from types import SimpleNamespace
    from workforce_suite.workforce_suite import statutory_native_data as native
    employees = [SimpleNamespace(name="TEST-LEFT", gender="Male", date_of_birth="1990-01-01",
                                 date_of_joining="2020-01-01", relieving_date="2026-06-01", status="Left"),
                 SimpleNamespace(name="TEST-PRIOR", gender="Female", date_of_birth="1990-01-01",
                                 date_of_joining="2020-01-01", relieving_date="2025-06-01", status="Left")]
    calls = []
    class FakeFrappe:
        @staticmethod
        def has_permission(*args):
            return True
        @staticmethod
        def get_list(doctype, **kwargs):
            calls.append((doctype, kwargs))
            if doctype == "Employee":
                return employees
            return [SimpleNamespace(employee="TEST-LEFT", attendance_date="2026-01-01", status="Present")]*2
    monkeypatch.setattr(native, "frappe", FakeFrappe)
    layout = SimpleNamespace(form_code="form_81", company="TEST-Company", branch="TEST-Branch")
    row = native.aggregate_periodic_return(layout, "2026-01-01", "2026-12-31")[0]
    assert calls[0][1]["filters"] == {"company": "TEST-Company", "branch": "TEST-Branch"}
    assert set(calls[1][1]["filters"]["employee"][1]) == {"TEST-LEFT"}
    assert calls[1][1]["filters"]["docstatus"] == 1
    assert row["adult_male"] == 1
    assert "leavers_other" not in row
    assert row["_period_provenance"]["observed_leavers"] == 1
    assert row["_period_provenance"]["observed_worker_days"] == 1
    assert not row["_period_provenance"]["attendance_coverage_complete"]
    assert {"HISTORICAL_ESTABLISHMENT_REVIEW", "ATTENDANCE_COVERAGE_REVIEW"} <= {f["code"] for f in row["_findings"]}
    monkeypatch.setattr(FakeFrappe, "has_permission", lambda *args: False)
    denied = native.aggregate_periodic_return(layout, "2026-01-01", "2026-12-31")[0]
    assert denied["_findings"][0]["code"] == "EMPLOYEE_ACCESS"
    assert len(calls) == 2


def test_periodic_checklist_is_idempotent_and_cannot_review_missing_fields(data):
    from workforce_suite.workforce_suite.statutory_setup import prepare_periodic_evidence
    doc=layout('form_80')
    names=[]
    try:
        first=prepare_periodic_evidence(doc.name,'2026-01-01','2026-06-30');names=first['records']
        again=prepare_periodic_evidence(doc.name,'2026-01-01','2026-06-30')
        assert first['created'] and not again['created'] and again['records']==names
        record=frappe.get_doc('Workforce Statutory Record',names[0])
        assert all(c.field_label for c in record.entries)
        assert any(c.value_status=='Unresolved' and not c.field_value for c in record.entries)
        frappe.set_user(data['reviewer'])
        with pytest.raises(frappe.ValidationError,match='justification'):record.submit()
        record.reload();record.evidence_note='TEST reviewed sources'
        with pytest.raises(frappe.ValidationError,match='required prescribed'):record.submit()
        frappe.set_user(data['unscoped'])
        with pytest.raises(frappe.PermissionError):prepare_periodic_evidence(doc.name,'2026-01-01','2026-06-30')
    finally:
        frappe.set_user('Administrator');frappe.db.rollback()
        for name in names:
            if frappe.db.exists('Workforce Statutory Record',name):
                # This test owns the unsubmitted draft created by the explicit commit action.
                frappe.db.delete('Workforce Statutory Value',{'parent':name})
                frappe.db.delete('Workforce Statutory Record',{'name':name,'docstatus':0})
        if frappe.db.exists(doc.doctype,doc.name):frappe.delete_doc(doc.doctype,doc.name)
        frappe.db.commit()


def test_service_history_requires_row_identity_and_preserves_dates(data):
    doc=layout('form_7')
    record=frappe.get_doc({'doctype':'Workforce Statutory Record','company':doc.company,'layout':doc.name,
        'employee':data['person'],'entry_date':'2026-10-01','evidence_note':'TEST source-backed service history',
        'entries':[{'field_key':'wage_effective','field_value':'2025-01-01','row_number':0}]})
    with pytest.raises(frappe.ValidationError,match='row numbers'):record.insert()
    record.entries[0].row_number=1
    record.insert()
    frappe.set_user(data['reviewer'])
    with pytest.raises(frappe.ValidationError,match='each entered history'):record.submit()


def test_payment_evidence_states_cannot_fabricate_money_or_cross_company(monkeypatch):
    from types import SimpleNamespace
    from workforce_suite.workforce_suite import statutory_financial_evidence as evidence
    class Item(SimpleNamespace):
        def get(self,key):return getattr(self,key,None)
    source=Item(name='TEST-SLIP',company='TEST-A',employee='TEST-E',docstatus=1,net_pay=100,
                check_permission=lambda *args:None)
    class FakeFrappe:
        PermissionError=PermissionError
        @staticmethod
        def get_doc(*args):return source
        @staticmethod
        def throw(message,*args):raise ValueError(message)
    monkeypatch.setattr(evidence,'frappe',FakeFrappe)
    record=Item(employee='TEST-E',company='TEST-A',evidence_kind='Worker Payment Evidenced',
                reference_doctype='Salary Slip',reference_name='TEST-SLIP',payment_date='2026-10-01',
                entry_date='2026-10-01',payment_reference='TEST-RECEIPT',payment_amount=100)
    evidence.validate_financial_evidence(record,Item(data_source='Salary Slip'))
    for amount in (0,-1,101,float('nan')):
        record.payment_amount=amount
        with pytest.raises(ValueError):evidence.validate_financial_evidence(record,Item(data_source='Salary Slip'))
    record.payment_amount=100;record.company='TEST-B'
    with pytest.raises(ValueError,match='scope'):evidence.validate_financial_evidence(record,Item(data_source='Salary Slip'))
    record.company='TEST-A';source.docstatus=0
    with pytest.raises(ValueError,match='submitted'):evidence.validate_financial_evidence(record,Item(data_source='Salary Slip'))
    source.docstatus=1;source.net_pay=0;record.payment_amount=0;record.evidence_kind='Worker Acknowledgement'
    evidence.validate_financial_evidence(record,Item(data_source='Salary Slip'))
    record.evidence_kind='Worker Payment Evidenced'
    with pytest.raises(ValueError,match='positive'):evidence.validate_financial_evidence(record,Item(data_source='Salary Slip'))
    source.net_pay=100;record.evidence_kind='Worker Acknowledgement'
    with pytest.raises(ValueError,match='positive'):evidence.validate_financial_evidence(record,Item(data_source='Salary Slip'))



def test_reviewed_period_calculation_requires_complete_calendar_attendance_and_independent_review(data):
    from datetime import timedelta
    from frappe.utils.file_manager import save_file
    doc=layout('form_80')
    token=frappe.generate_hash(8)
    file=save_file('TEST-workforce-'+token+'.txt',b'TEST historical membership and establishment calendar',None,None,is_private=1)
    owned_path=Path(file.get_full_path())
    try:
        for day in ('2026-01-01','2026-01-02'):
            frappe.get_doc({'doctype':'Attendance','employee':data['person'],'company':doc.company,
                'attendance_date':day,'status':'Present','working_hours':8}).insert().submit()
        member={'employee':data['person'],'worker_category':'Adult Male','effective_from':'2026-01-01',
                'effective_to':'2026-06-30','source_reference':'TEST source-backed membership including transfer review'}
        record=frappe.get_doc({'doctype':'Workforce Statutory Record','company':doc.company,'layout':doc.name,
            'entry_date':'2026-06-30','reporting_from':'2026-01-01','reporting_to':'2026-06-30',
            'calculation_mode':'Reviewed Workforce Evidence','workforce_coverage_attested':1,
            'workforce_members':[member],'evidence_file':file.file_url,'evidence_note':'TEST independently checked complete scope',
            'entries':[{'field_key':c.field_key,'field_value':'TEST evidence','value_status':'Evidence Entered'} for c in doc.columns]}).insert()
        assert record.calculation_provenance.startswith('Unresolved')
        for n in range(181):
            day=date(2026,1,1)+timedelta(days=n)
            record.append('workforce_calendar',{'work_date':day,'is_working_day':n<2,'source_reference':'TEST reviewed calendar'})
        record.save()
        assert {c.field_key:c.field_value for c in record.entries}['adult_male']=='1.00'
        assert 'submitted_attendance_sha256' in record.calculation_provenance
        with pytest.raises(frappe.PermissionError):record.submit()
        frappe.set_user(data['reviewer']);record.reload();record.submit();frappe.set_user('Administrator')
        assert forms.preview_a4(doc.name,'2026-01-01','2026-06-30')['row_count']==1
        # A missing third working-day observation remains unresolved, never absence.
        draft=frappe.copy_doc(record);draft.docstatus=0;draft.name=None
        draft.workforce_calendar[2].is_working_day=1;draft.insert()
        assert draft.calculation_provenance.startswith('Unresolved')
        frappe.set_user(data['reviewer'])
        with pytest.raises(frappe.ValidationError,match='Incomplete submitted Attendance'):draft.submit()
    finally:
        owned_path.unlink(missing_ok=True)


def test_worker_manual_register_filters_canonical_employee_without_exposing_establishment_evidence(data):
    doc=layout('form_39')
    record=frappe.get_doc({'doctype':'Workforce Statutory Record','company':doc.company,'layout':doc.name,
        'employee':data['person'],'entry_date':'2026-01-01','evidence_note':'TEST worker-specific native identity and reviewed incident',
        'entries':[{'field_key':'remarks','field_value':'TEST worker-specific reviewed facts'}]}).insert()
    frappe.set_user(data['reviewer']);record.submit();frappe.set_user('Administrator')
    assert forms.preview_a4(doc.name,'2026-01-01','2026-01-31',employee=data['person'])['row_count']==1
    with pytest.raises(frappe.PermissionError):forms.preview_a4(doc.name,'2026-01-01','2026-01-31',employee=data['other'])


def test_reviewed_overtime_rates_match_each_native_interval_and_currency_precision(monkeypatch):
    from types import SimpleNamespace
    from workforce_suite.workforce_suite import statutory_financial_evidence as evidence
    class Item(SimpleNamespace):
        def get(self,key):return getattr(self,key,None)
    slip=Item(name='TEST-OT',employee='TEST-E',company='TEST-A',docstatus=1,
        start_date='2026-09-01',end_date='2026-09-30',check_permission=lambda *a:None,
        overtime_details=[Item(date='2026-09-02',overtime_duration=2),Item(date='2026-09-12',overtime_duration=3)])
    salary=Item(check_permission=lambda *a:None,precision=lambda field:3)
    class FakeFrappe:
        PermissionError=PermissionError
        @staticmethod
        def get_doc(doctype,name):return slip if doctype=='Overtime Slip' else salary
        @staticmethod
        def get_list(*a,**kw):return [Item(name='TEST-AS',amount='80.005',salary_component='TEST-OT')]
        @staticmethod
        def throw(message,*a):raise ValueError(message)
    monkeypatch.setattr(evidence,'frappe',FakeFrappe)
    rates=[Item(effective_from='2026-09-01',effective_to='2026-09-09',hours=2,hourly_rate='10.001',amount='20.002',source_reference='TEST-first'),
           Item(effective_from='2026-09-10',effective_to='2026-09-30',hours=3,hourly_rate='20.001',amount='60.003',source_reference='TEST-second')]
    record=Item(employee='TEST-E',company='TEST-A',evidence_kind='Overtime Rate Breakdown',
                reference_doctype='Overtime Slip',reference_name='TEST-OT',rates=rates)
    evidence.validate_financial_evidence(record,Item(data_source='Attendance'))
    rates[0].amount='20.003'
    with pytest.raises(ValueError,match='amount'):evidence.validate_financial_evidence(record,Item(data_source='Attendance'))
    rates[0].amount='20.002';rates[0].effective_to='2026-09-15'
    with pytest.raises(ValueError,match='interval hours'):evidence.validate_financial_evidence(record,Item(data_source='Attendance'))
    rates[0].effective_to='2026-09-09';rates[1].effective_from='2026-09-01'
    with pytest.raises(ValueError,match='one evidenced'):evidence.validate_financial_evidence(record,Item(data_source='Attendance'))


def test_reviewed_original_fingerprint_rejects_replaced_and_non_image_content(monkeypatch):
    from types import SimpleNamespace
    from workforce_suite.workforce_suite import statutory_evidence_files as evidence
    file=SimpleNamespace(name='TEST-FILE',check_permission=lambda *a:None,get_content=lambda:b'TEST original')
    class FakeFrappe:
        PermissionError=PermissionError
        @staticmethod
        def get_doc(*a):return file
        @staticmethod
        def get_list(*a,**kw):return [SimpleNamespace(name='TEST-FILE',is_private=1)]
        @staticmethod
        def throw(message,*a):raise ValueError(message)
    monkeypatch.setattr(evidence,'frappe',FakeFrappe)
    _,digest,_=evidence.checked_original('TEST-PRIVATE')
    file.get_content=lambda:b'TEST replaced'
    with pytest.raises(ValueError,match='changed'):evidence.checked_original('TEST-PRIVATE',digest)
    with pytest.raises(ValueError,match='PNG or JPEG'):evidence.checked_original('TEST-PRIVATE',image_only=True)
    file.get_content=lambda:b'\x89PNG\r\n\x1a\nTEST corrupt payload'
    with pytest.raises(ValueError,match='readable PNG or JPEG'):evidence.checked_original('TEST-PRIVATE',image_only=True)
    from io import BytesIO
    from PIL import Image
    buffer=BytesIO();Image.new('RGB',(2,2),'white').save(buffer,format='PNG')
    file.get_content=lambda:buffer.getvalue()
    assert evidence.checked_original('TEST-PRIVATE',image_only=True)[0]==buffer.getvalue()



def test_native_evidence_choices_expose_companions_and_reject_unrelated_form_keys(data):
    from workforce_suite.workforce_suite.statutory_setup import evidence_field_options
    company='Example Company A';employee=data['person']
    form=layout('form_8',company)
    options=evidence_field_options(form.name)
    assert {'national_id','grade'} <= {value['key'] for value in options['fields']}
    with pytest.raises(frappe.ValidationError,match='Unknown or native-owned'):
        frappe.get_doc({'doctype':'Workforce Statutory Record','company':company,'layout':form.name,
            'employee':employee,'entry_date':'2026-09-01','entries':[{'field_key':'probation_terms','field_value':'TEST unrelated'}]}).insert()


def test_service_book_same_date_different_employers_survive_but_conflicting_versions_block(data):
    book=layout('form_7')
    for employer in ('TEST Employer A','TEST Employer B'):
        record=frappe.get_doc({'doctype':'Workforce Statutory Record','layout':book.name,
            'company':'Example Company A','employee':data['person'],'entry_date':'2026-09-01',
            'evidence_note':'TEST independent historical service original',
            'entries':[{'field_key':key,'field_value':value,'row_number':1,'value_status':'Evidence Entered',
                        'source_reference':'TEST original employment history'} for key,value in {
                'history_establishment':employer,'history_employer':employer,
                'history_joined':'2020-01-01','history_left':'2020-06-30','history_left_reason':'TEST reviewed reason'}.items()]}).insert()
        frappe.set_user(data['reviewer']);record.submit();frappe.set_user('Administrator')
    _,_,context=forms._print_context(book.name,employee=data['person'])
    entries=context['rows'][0]['_history']['employment_history']
    assert len(entries)==2 and {entry['history_employer'] for entry in entries}=={'TEST Employer A','TEST Employer B'}
    duplicate=frappe.copy_doc(record);duplicate.owner='Administrator';duplicate.entries[-1].field_value='TEST conflicting reason';duplicate.insert()
    frappe.set_user(data['reviewer']);duplicate.submit();frappe.set_user('Administrator')
    with pytest.raises(frappe.ValidationError,match='Overlapping reviewed service-history'):
        forms._print_context(book.name,employee=data['person'])
