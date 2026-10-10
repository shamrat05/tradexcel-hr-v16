import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "frappe-bench" / "apps"
sys.path.insert(0, str(APP_ROOT))

from workforce_suite.workforce_suite.report.daily_attendance_summary.daily_attendance_summary import (
    normalize_filters,
)


def test_normalize_filters_supplies_optional_values_for_direct_api_calls():
    filters = normalize_filters(
        {"attendance_date": "2026-09-16", "company": "Example Company A"}
    )

    assert filters.department == ""
    assert filters.branch == ""
    assert filters.status == ""


def test_normalize_filters_preserves_explicit_optional_values():
    filters = normalize_filters(
        {
            "attendance_date": "2026-09-16",
            "company": "Example Company A",
            "department": "Factory",
            "branch": "Example Factory",
            "status": "Present",
        }
    )

    assert filters.department == "Factory"
    assert filters.branch == "Example Factory"
    assert filters.status == "Present"


def test_normalize_filters_rejects_missing_required_values():
    with pytest.raises(ValueError, match="attendance_date"):
        normalize_filters({"company": "Example Company A"})


def test_normalize_filters_maps_legacy_single_date_to_a_one_day_range():
    filters = normalize_filters(
        {"attendance_date": "2026-09-16", "company": "Example Company A"}
    )

    assert filters.from_date == "2026-09-16"
    assert filters.to_date == "2026-09-16"


def test_normalize_filters_accepts_a_month_range():
    filters = normalize_filters(
        {
            "from_date": "2026-09-01",
            "to_date": "2026-09-30",
            "company": "Example Company A",
        }
    )

    assert filters.from_date == "2026-09-01"
    assert filters.to_date == "2026-09-30"


def test_normalize_filters_rejects_inverted_or_unbounded_ranges():
    with pytest.raises(ValueError, match="from_date"):
        normalize_filters(
            {
                "from_date": "2026-09-30",
                "to_date": "2026-09-01",
                "company": "Example Company A",
            }
        )

    with pytest.raises(ValueError, match="366"):
        normalize_filters(
            {
                "from_date": "2026-01-01",
                "to_date": "2027-01-03",
                "company": "Example Company A",
            }
        )
