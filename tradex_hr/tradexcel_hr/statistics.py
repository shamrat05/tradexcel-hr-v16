"""Cohort-relative robust statistics for the anomaly radar. Pure functions only."""

from __future__ import annotations

from statistics import median


MODIFIED_Z_SCALE = 0.6745


def center_and_spread(values):
    """Median and median absolute deviation (MAD)."""
    center = median(values)
    spread = median([abs(value - center) for value in values])
    return center, spread


def cohort_findings(observations, threshold, min_cohort):
    """Flag values far from their cohort median.

    observations: dicts with key, cohort, value plus arbitrary payload.
    Zero-spread cohorts flag any deviation; small cohorts are skipped.
    """
    groups = {}
    for row in observations:
        groups.setdefault(row["cohort"], []).append(row)
    findings = []
    for cohort in sorted(groups):
        rows = groups[cohort]
        if len(rows) < min_cohort:
            continue
        center, spread = center_and_spread([row["value"] for row in rows])
        for row in rows:
            if spread > 0:
                z = MODIFIED_Z_SCALE * (row["value"] - center) / spread
                if abs(z) >= threshold:
                    findings.append({"row": row, "center": center, "z": z})
            elif row["value"] != center:
                findings.append({"row": row, "center": center, "z": None})
    return findings


def relative_change(current, previous):
    if not previous:
        return None
    return (current - previous) / previous


def trend_outliers(observations, threshold, min_cohort, min_previous):
    """Flag cohort-relative changes between the period and the previous period.

    observations: dicts with key, cohort, current, previous, plus payload.
    Employees below min_previous activity are skipped so low counts do not
    produce giant percentages.
    """
    prepared = []
    for row in observations:
        change = relative_change(row["current"], row["previous"])
        if change is None or row["previous"] < min_previous:
            continue
        prepared.append({**row, "change": change})
    changes_by_cohort = {}
    for row in prepared:
        changes_by_cohort.setdefault(row["cohort"], []).append(row["change"])
    findings = []
    for row in prepared:
        peers = changes_by_cohort[row["cohort"]]
        if len(peers) < min_cohort:
            continue
        center, spread = center_and_spread(peers)
        if spread == 0:
            continue
        z = MODIFIED_Z_SCALE * (row["change"] - center) / spread
        if abs(z) >= threshold:
            findings.append({"row": row, "center": center, "z": z})
    return findings
