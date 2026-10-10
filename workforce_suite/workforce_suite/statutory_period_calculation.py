"""Opt-in averages from reviewed historical membership and complete work evidence.

The establishment calendar and worker classification are independently reviewed
inputs. Native submitted Attendance owns observed work; no missing day is absence.
"""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

CATEGORIES = {'Adult Male':'adult_male','Adult Female':'adult_female',
              'Adolescent Boy':'adolescent_boys','Adolescent Girl':'adolescent_girls'}


def calculate_period_workforce(members, calendar, attendance, start, end):
    from datetime import date
    def at(value): return value if isinstance(value,date) else date.fromisoformat(str(value))
    start,end=at(start),at(end)
    days={}
    for row in calendar:
        day=at(row.work_date)
        if day in days or not start<=day<=end:
            raise ValueError('Calendar dates must be unique and within the complete return period')
        if not row.source_reference:
            raise ValueError('Each calendar decision requires source provenance')
        days[day]=bool(row.is_working_day)
    expected={start+timedelta(days=n) for n in range((end-start).days+1)}
    if set(days)!=expected:
        raise ValueError('Reviewed calendar must cover every date; omitted dates are not holidays')
    working={d for d,v in days.items() if v}
    if not working:
        raise ValueError('No working-day denominator is evidenced; do not invent a zero average')
    observations={}
    for row in attendance:
        key=(row.employee,at(row.attendance_date))
        if row.status not in {'Present','Half Day','Work From Home','Absent','On Leave'}:
            raise ValueError('Unresolved Attendance status prevents complete work observations')
        value=row.status in {'Present','Half Day','Work From Home'}
        # Multiple shifts represent one identity/day; conflicting work versus
        # non-work shifts need source review rather than arbitrary precedence.
        if key in observations and observations[key]!=value:
            raise ValueError('Conflicting submitted Attendance on the same worker/date')
        observations[key]=value
    totals={key:Decimal(0) for key in CATEGORIES.values()}
    totals.update({key:Decimal(0) for key in ('foreign_male','foreign_female','contractor_male','contractor_female')})
    identities=set();missing=0;person_days=0
    for member in members:
        category=CATEGORIES.get(member.worker_category)
        if not category or not member.source_reference:
            raise ValueError('Every historical worker category requires explicit reviewed evidence')
        first,last=at(member.effective_from),at(member.effective_to)
        if first>last or first<start or last>end:
            raise ValueError('Membership intervals must be clipped to the exact return period')
        employee=member.employee
        external=member.external_identifier
        if bool(employee)==bool(external):
            raise ValueError('Choose one native Employee or one explicit external workforce identity')
        active={day for day in working if first<=day<=last}
        identity=('employee' if employee else 'external',employee or external)
        for day in active:
            if (identity,day) in identities:
                raise ValueError('Overlapping worker/establishment membership would double-count a date')
            identities.add((identity,day))
        if employee:
            unknown=[day for day in active if (employee,day) not in observations]
            missing+=len(unknown)
            count=sum(observations.get((employee,day),False) for day in active)
        else:
            raw=member.external_workdays
            if raw in (None,''):
                raise ValueError('External workforce workdays require reviewed evidence, never an assumed zero')
            count=Decimal(str(raw))
            if not count.is_finite() or count<0 or count!=count.to_integral_value() or count>len(active):
                raise ValueError('External workdays must be an evidenced whole count within membership working days')
        totals[category]+=Decimal(count);person_days+=int(count)
        gender='male' if member.worker_category in ('Adult Male','Adolescent Boy') else 'female'
        if member.is_foreign:totals['foreign_'+gender]+=Decimal(count)
        if member.is_contractor:totals['contractor_'+gender]+=Decimal(count)
    if not members:
        raise ValueError('Review the actual workforce population; empty input is not a verified zero workforce')
    if missing:
        raise ValueError(f'Incomplete submitted Attendance coverage: {missing} employee working-days unresolved')
    values={key:str((value/len(working)).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)) for key,value in totals.items()}
    return values,{'method':'Unique submitted work-status worker-days / independently reviewed establishment working dates',
                   'working_days':len(working),'calendar_days':len(days),'worker_days':person_days,
                   'missing_observations':0,'membership_intervals':len(members),'scope_completeness':'Independent HR attestation, not inferred current headcount'}


def resolve_record_workforce(record, layout):
    import frappe
    from frappe.utils import getdate
    if record.get('calculation_mode')!='Reviewed Workforce Evidence':return None
    if layout.form_code not in {'form_80','form_81'}:
        raise ValueError('Workforce averaging belongs only to periodic returns')
    if not record.get('workforce_coverage_attested') or not record.get('evidence_file'):
        raise ValueError('Attest complete establishment membership/calendar evidence and attach its private source')
    members=record.get('workforce_members') or [];calendar=record.get('workforce_calendar') or []
    if len(members)>2000 or len(calendar)>371:raise ValueError('Narrow the establishment evidence; nothing was truncated')
    first,last=record.get('reporting_from'),record.get('reporting_to')
    employees=[]
    for member in members:
        if member.employee:
            person=frappe.get_doc('Employee',member.employee);person.check_permission('read')
            # Current Company/Branch deliberately does not decide historical
            # membership. The independently reviewed source owns that decision.
            if not person.date_of_joining or (person.status!='Active' and not person.relieving_date):
                raise ValueError('Reliable native employment dates are missing; resolve dates or use reviewed aggregate values')
            if getdate(member.effective_from)<getdate(person.date_of_joining) or (person.relieving_date and getdate(member.effective_to)>getdate(person.relieving_date)):
                raise ValueError('Historical membership conflicts with authoritative employment dates')
            employees.append(member.employee)
    if employees and not frappe.has_permission('Attendance','read'):
        frappe.throw('Submitted Attendance access is required for workforce calculation',frappe.PermissionError)
    attendance=frappe.get_list('Attendance',filters={'company':record.company,'employee':['in',list(set(employees))],
        'docstatus':1,'attendance_date':['between',[first,last]]},fields=['name','employee','attendance_date','status'],
        limit_page_length=500001) if employees else []
    if len(attendance)>500000:raise ValueError('Attendance calculation boundary exceeded; use reviewed aggregates with provenance')
    try:values,provenance=calculate_period_workforce(members,calendar,attendance,first,last)
    except (ValueError,TypeError):raise
    import hashlib, json
    provenance['submitted_attendance_count'] = len(attendance)
    provenance['submitted_attendance_sha256'] = hashlib.sha256(json.dumps(
        sorted([dict(row) for row in attendance], key=lambda row: row['name']),
        sort_keys=True, default=str).encode()).hexdigest()
    values['working_days' if layout.form_code=='form_80' else 'annual_working_days']=str(provenance['working_days'])
    return values,provenance
