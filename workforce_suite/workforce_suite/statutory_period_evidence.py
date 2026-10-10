"""Historical employment observations, separate from prescribed legal categories.

Current organizational assignments are candidate filters, never proof of past
establishment membership. Returned statistics must remain review observations.
"""
from datetime import date


def _date(value):
    if not value:
        return None
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def employment_observations(employees, start, end):
    start, end = _date(start), _date(end)
    if not start or not end or end < start:
        raise ValueError("A valid reporting period is required")
    candidates, intervals, incomplete = {}, {}, []
    for person in employees:
        identity = person.name
        if identity in candidates:
            raise ValueError("Duplicate Employee identity in historical workforce")
        joined = _date(getattr(person, "date_of_joining", None))
        left = _date(getattr(person, "relieving_date", None))
        if joined and left and left < joined:
            incomplete.append(identity)
            continue
        if (joined and joined > end) or (left and left < start):
            continue
        candidates[identity] = person
        # An inactive worker without a relieving date has no established end.
        if not joined or (getattr(person, "status", "Active") != "Active" and not left):
            incomplete.append(identity)
            continue
        intervals[identity] = (max(start, joined), min(end, left or end))
    joiners = sum(start <= _date(p.date_of_joining) <= end for p in candidates.values()
                  if p.name in intervals)
    leavers = sum(start <= _date(p.relieving_date) <= end for p in candidates.values()
                  if p.name in intervals and getattr(p, "relieving_date", None))
    return candidates, intervals, {
        "period_start": start.isoformat(), "period_end": end.isoformat(),
        "candidate_count": len(candidates), "dated_candidate_count": len(intervals),
        "observed_joiners": joiners, "observed_leavers": leavers,
        "employment_dates_complete": not incomplete,
        "establishment_history_verified": False,
        "missing_employment_date_count": len(incomplete),
    }
