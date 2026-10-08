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
        'review_notes':'TEST no legal certification'}).insert()
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
    approved_copy=frappe.get_doc({'doctype':'Workforce Statutory Profile','company':'Example Company B','profile_version':'1','effective_from':'2020-01-01','establishment_en':'TEST','address_en':'TEST','legal_reference':'TEST','review_notes':'TEST'}).insert()
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
        'entry_date':'2026-10-02','entries':[{'field_key':c.field_key,'field_value':'TEST '+c.field_key} for c in doc.columns],
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
        'entry_date':'2026-01-01','evidence_note':'TEST establishment-wide sensitive evidence',
        'entries':[{'field_key':'licence_no','field_value':'TEST-MANUAL-RESTRICTED'}]}).insert()
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
        'entry_date':'2026-01-01','evidence_note':'TEST reviewed establishment evidence',
        'entries':[{'field_key':'licence_no','field_value':'TEST-MATCHING-BRANCH'}]}).insert()
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
        names = first['layouts']; assert first['created'] and len(names) == 1
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
        with pytest.raises(frappe.ValidationError):
            prepare_draft_layout('Example Company A', 'form_32', '2026-10-01', branch.name)
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
