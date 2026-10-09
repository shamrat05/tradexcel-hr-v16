from types import SimpleNamespace

import pytest

from workforce_suite.workforce_suite.statutory_period_evidence import employment_observations


def person(name, joined="2020-01-01", left=None, status="Active"):
    return SimpleNamespace(name=name, date_of_joining=joined, relieving_date=left, status=status)


def test_period_selection_includes_joiners_and_currently_left_workers():
    people = [person("continuing"), person("joiner", "2026-03-01"),
              person("leaver", left="2026-06-30", status="Left"),
              person("prior", left="2025-12-31", status="Left"),
              person("future", "2027-01-01")]
    selected, intervals, evidence = employment_observations(people, "2026-01-01", "2026-12-31")
    assert set(selected) == {"continuing", "joiner", "leaver"}
    assert str(intervals["joiner"][0]) == "2026-03-01"
    assert str(intervals["leaver"][1]) == "2026-06-30"
    assert evidence["observed_joiners"] == evidence["observed_leavers"] == 1
    assert evidence["employment_dates_complete"]
    assert not evidence["establishment_history_verified"]


def test_missing_dates_never_become_complete_history():
    people = [person("unknown-start", None), person("unknown-end", status="Left"),
              person("inconsistent", "2026-06-01", "2026-01-01", "Left")]
    selected, intervals, evidence = employment_observations(people, "2026-01-01", "2026-12-31")
    assert set(selected) == {"unknown-start", "unknown-end"}
    assert not intervals
    assert evidence["missing_employment_date_count"] == 3
    assert not evidence["employment_dates_complete"]
    assert evidence["observed_leavers"] == 0


def test_boundaries_are_inclusive_and_duplicate_identities_fail():
    _, _, evidence = employment_observations([person("boundary", "2026-01-01", "2026-12-31", "Left")], "2026-01-01", "2026-12-31")
    assert evidence["observed_joiners"] == evidence["observed_leavers"] == 1
    with pytest.raises(ValueError, match="Duplicate"):
        employment_observations([person("same"), person("same")], "2026-01-01", "2026-12-31")
    with pytest.raises(ValueError, match="valid reporting"):
        employment_observations([], "2026-12-31", "2026-01-01")
