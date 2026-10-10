"""Reviewed payment/rate evidence; never creates or changes financial records."""
from decimal import Decimal, ROUND_HALF_UP

import frappe
from frappe.utils import getdate

KINDS = {'Payment Instructed', 'Payment Reconciled', 'Worker Payment Evidenced',
         'Worker Acknowledgement', 'Overtime Rate Breakdown'}


def validate_financial_evidence(record, layout):
    kind = record.get('evidence_kind') or 'Supplemental Facts'
    if kind not in KINDS:
        if record.get('rates'):
            frappe.throw('Rate rows require Overtime Rate Breakdown evidence.')
        return
    if layout.data_source not in {'Attendance', 'Salary Slip'} or not record.employee:
        frappe.throw('Financial evidence requires a native worker wage/overtime layout.')
    expected = 'Overtime Slip' if kind == 'Overtime Rate Breakdown' else 'Salary Slip'
    if record.get('reference_doctype') != expected or not record.get('reference_name'):
        frappe.throw('Link the authoritative submitted source for this evidence.')
    source = frappe.get_doc(expected, record.reference_name)
    source.check_permission('read')
    if source.docstatus != 1 or source.employee != record.employee or source.company != record.company:
        frappe.throw('Financial evidence source is outside the submitted worker/company scope.', frappe.PermissionError)
    if record.get('entries'):
        frappe.throw('Financial evidence cannot override native print values.')
    if kind == 'Overtime Rate Breakdown':
        rows = record.get('rates') or []
        if not rows or len(rows) > 200:
            frappe.throw('Enter a bounded historical overtime rate breakdown.')
        amounts = frappe.get_list('Additional Salary', filters={'employee': record.employee, 'company': record.company,
            'docstatus': 1, 'ref_doctype': 'Overtime Slip', 'ref_docname': source.name}, fields=['name','amount','salary_component'], limit_page_length=201)
        if not amounts or len(amounts)>200 or len({r.salary_component for r in amounts}) != len(amounts):
            frappe.throw('Unambiguous submitted native overtime amounts are required.')
        precisions = set()
        for item in amounts:
            salary = frappe.get_doc('Additional Salary', item.name)
            salary.check_permission('read')
            precisions.add(salary.precision('amount'))
        if len(precisions) != 1 or None in precisions:
            frappe.throw('Resolve the native currency precision before reviewing rates.')
        quantum = Decimal(1).scaleb(-precisions.pop())
        def rounded(value): return value.quantize(quantum, rounding=ROUND_HALF_UP)
        hours = Decimal(0)
        amount = Decimal(0)
        covered_dates = set()
        for row in rows:
            if not row.effective_from or not row.effective_to or not row.source_reference:
                frappe.throw('Each rate needs effective dates and original rate evidence reference.')
            first, last = getdate(row.effective_from), getdate(row.effective_to)
            if first > last or first < getdate(source.start_date) or last > getdate(source.end_date):
                frappe.throw('Rate evidence dates must be within its complete native Overtime Slip.')
            numbers = [Decimal(str(row.get(key) or 0)) for key in ('hours', 'hourly_rate', 'amount')]
            if any(not n.is_finite() or n < 0 for n in numbers) or numbers[0] <= 0:
                frappe.throw('Historical rate evidence requires finite positive hours and non-negative money.')
            if rounded(numbers[0]*numbers[1]) != rounded(numbers[2]):
                frappe.throw('Reviewed rate/hours do not reconcile with the evidenced amount.')
            details = [detail for detail in source.overtime_details if first <= getdate(detail.date) <= last]
            dates = {getdate(detail.date) for detail in details}
            if not details or covered_dates.intersection(dates):
                frappe.throw('Each native overtime date must belong to one evidenced rate interval.')
            if numbers[0] != sum((Decimal(str(detail.overtime_duration or 0)) for detail in details), Decimal(0)):
                frappe.throw('Rate interval hours must match its actual approved overtime dates.')
            covered_dates.update(dates)
            hours += numbers[0]; amount += numbers[2]
        approved_hours = sum((Decimal(str(r.overtime_duration or 0)) for r in source.overtime_details), Decimal(0))
        if hours != approved_hours:
            frappe.throw('Rate breakdown hours must reconcile with the complete approved Overtime Slip.')
        if rounded(amount) != rounded(sum((Decimal(str(r.amount)) for r in amounts), Decimal(0))):
            frappe.throw('Reviewed rate amounts must reconcile with native Additional Salary.')
    else:
        if record.get('rates'):
            frappe.throw('Payment/acknowledgement evidence cannot carry rate rows.')
        if not record.get('payment_date') or not record.get('payment_reference'):
            frappe.throw('Record the actual evidence date and payment/acknowledgement reference.')
        if getdate(record.payment_date) > min(getdate(record.entry_date), getdate()):
            frappe.throw('Evidence cannot attest a future payment or acknowledgement.')
        value = Decimal(str(record.get('payment_amount') or 0))
        net = Decimal(str(source.net_pay))
        zero_acknowledgement = kind == 'Worker Acknowledgement' and value == 0 and net == 0
        if not value.is_finite() or (value <= 0 and not zero_acknowledgement) or value > net:
            frappe.throw('Evidence amount must be positive and cannot exceed linked net wages, except an acknowledgement of exactly zero native net pay.')


def reviewed_financial_evidence(layout, employee, source_names, start, end):
    if not source_names or not frappe.has_permission('Workforce Statutory Record', 'read'):
        return []
    names=frappe.get_list('Workforce Statutory Record', filters={'layout': layout.name,
        'company': layout.company, 'employee': employee, 'docstatus':1,
        'reference_name':['in',source_names], 'evidence_kind':['in',list(KINDS)]},
        fields=['name'], limit_page_length=201)
    if len(names)>200:
        frappe.throw('Too many financial evidence versions; resolve the reporting scope.')
    output=[]
    for item in names:
        record=frappe.get_doc('Workforce Statutory Record',item.name);record.check_permission('read')
        if not record.reviewed_by or record.reviewed_by==record.owner:
            frappe.throw('Financial evidence needs an independent recorded reviewer.')
        validate_financial_evidence(record,layout)
        files = frappe.get_list('File', filters={'file_url': record.evidence_file}, fields=['name','is_private'], limit_page_length=2)
        if len(files) != 1 or not files[0].is_private:
            frappe.throw('Financial originals must remain readable and private.', frappe.PermissionError)
        frappe.get_doc('File', files[0].name).check_permission('read')
        from workforce_suite.workforce_suite.statutory_evidence_files import checked_original
        checked_original(record.evidence_file, record.get('evidence_sha256') or '')
        output.append(record)
    # Duplicate reviewed statements cannot silently become additional payments.
    identities=[(r.evidence_kind,r.reference_name,r.get('payment_reference') or '') for r in output]
    if len(identities)!=len(set(identities)):
        frappe.throw('Duplicate active financial evidence needs explicit reviewer resolution.')
    return output


def apply_financial_evidence(layout, row, start, end):
    source_names=([row['salary_slip']] if row.get('salary_slip') else []) + row.get('_overtime',[])
    evidence=reviewed_financial_evidence(layout,row.get('employee'),source_names,start,end)
    row['_financial_evidence']=[r.name for r in evidence]
    rate_records=[r for r in evidence if r.evidence_kind=='Overtime Rate Breakdown']
    if rate_records:
        row['_rate_rows'] = [{'worker': row.get('employee_name') or row.get('employee'),
            'from': value.effective_from, 'to': value.effective_to, 'hours': value.hours,
            'rate': value.hourly_rate, 'amount': value.amount, 'reference': value.source_reference}
            for record in rate_records for value in record.rates]
        rates={Decimal(str(v.hourly_rate)) for r in rate_records for v in r.rates}
        if len(rates)==1 and len(rate_records)==len(row.get("_overtime", [])):
            row['overtime_hourly_rate' if layout.form_code=='form_34' else 'overtime_rate']=str(next(iter(rates)))
        else:
            row.setdefault('_findings',[]).append({'code':'MIXED_RATE_BREAKDOWN','message':'Reviewed mixed historical rates are retained as evidence; no single blended rate is printed.'})
    if row.get('salary_slip'):
        paid=[r for r in evidence if r.evidence_kind=='Worker Payment Evidenced']
        acknowledged=[r for r in evidence if r.evidence_kind=='Worker Acknowledgement']
        net=Decimal(str(row['net_pay']))
        total=sum((Decimal(str(r.payment_amount)) for r in paid),Decimal(0))
        if total>net:
            frappe.throw('Reviewed worker payment evidence exceeds linked net wages.')
        row['_payment_rows']=[{'worker': row.get('employee_name') or row.get('employee'), 'state': r.evidence_kind, 'date': r.payment_date, 'amount': r.payment_amount, 'reference': r.payment_reference} for r in evidence if r.evidence_kind!='Overtime Rate Breakdown']
        row['_worker_payment_status']='Fully Evidenced' if paid and total==net else ('Partially Evidenced' if paid else 'Unverified')
        if acknowledged:
            if len(acknowledged)>1:
                frappe.throw('Multiple worker acknowledgement versions require review.')
            row['acknowledgement']=f'{acknowledged[0].payment_date} / {acknowledged[0].payment_reference}'
    return row
