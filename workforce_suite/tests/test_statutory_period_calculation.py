from types import SimpleNamespace as Row
import pytest
from workforce_suite.workforce_suite.statutory_period_calculation import calculate_period_workforce


def calendar():
    return [Row(work_date=f'2026-01-0{i}',is_working_day=i!=3,source_reference='TEST reviewed calendar') for i in range(1,4)]


def member(employee='TEST-E',category='Adult Male',start='2026-01-01',end='2026-01-03',external=''):
    return Row(employee=employee,external_identifier=external,worker_category=category,
               effective_from=start,effective_to=end,source_reference='TEST historical membership',
               is_foreign=0,is_contractor=0,external_workdays=None)


def test_complete_reviewed_population_includes_joiner_leaver_and_distinct_dates():
    workers=[member(end='2026-01-01'),member('TEST-J','Adult Female',start='2026-01-02')]
    observations=[Row(employee='TEST-E',attendance_date='2026-01-01',status='Present')]*2
    observations += [Row(employee='TEST-J',attendance_date='2026-01-02',status='Present')]
    values,proof=calculate_period_workforce(workers,calendar(),observations,'2026-01-01','2026-01-03')
    assert values['adult_male']==values['adult_female']=='0.50'
    assert proof['worker_days']==2 and proof['working_days']==2
    assert proof['missing_observations']==0


def test_missing_attendance_is_never_absence_and_conflicting_shifts_need_review():
    observations=[Row(employee='TEST-E',attendance_date='2026-01-01',status='Present')]
    with pytest.raises(ValueError,match='Incomplete'):calculate_period_workforce([member()],calendar(),observations,'2026-01-01','2026-01-03')
    observations += [Row(employee='TEST-E',attendance_date='2026-01-02',status='Absent')]
    values,_=calculate_period_workforce([member()],calendar(),observations,'2026-01-01','2026-01-03')
    assert values['adult_male']=='0.50'
    observations += [Row(employee='TEST-E',attendance_date='2026-01-02',status='Present')]
    with pytest.raises(ValueError,match='Conflicting'):calculate_period_workforce([member()],calendar(),observations,'2026-01-01','2026-01-03')


def test_calendar_and_classification_and_external_workforce_are_explicit():
    worker=member(employee='',external='TEST-CONTRACTOR');worker.is_contractor=1
    with pytest.raises(ValueError,match='never an assumed zero'):calculate_period_workforce([worker],calendar(),[],'2026-01-01','2026-01-03')
    worker.external_workdays='1'
    values,_=calculate_period_workforce([worker],calendar(),[],'2026-01-01','2026-01-03')
    assert values['contractor_male']=='0.50'
    with pytest.raises(ValueError,match='every date'):calculate_period_workforce([worker],calendar()[:-1],[],'2026-01-01','2026-01-03')
    with pytest.raises(ValueError,match='double-count'):calculate_period_workforce([worker,worker],calendar(),[],'2026-01-01','2026-01-03')
    worker.worker_category='Pending Review'
    with pytest.raises(ValueError,match='explicit reviewed'):calculate_period_workforce([worker],calendar(),[],'2026-01-01','2026-01-03')
