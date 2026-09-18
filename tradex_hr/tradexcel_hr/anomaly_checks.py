"""Pure anomaly checks. Each check reads a prepared context and returns findings."""

from __future__ import annotations

from statistics import median

from tradex_hr.tradexcel_hr.statistics import cohort_findings, trend_outliers


FINDING_KEYS = (
    "category", "severity", "scope", "subject", "employee", "metric",
    "observed", "baseline", "deviation", "detail", "action",
)
SEVERITY_RANK = {"High": 0, "Medium": 1, "Low": 2}
PRESENT_STATUSES = {"Present", "Half Day", "Work From Home"}


def validate_finding(finding):
    missing = [key for key in FINDING_KEYS if key not in finding]
    if missing:
        raise ValueError(f"Finding is missing keys: {missing}")
    return finding


def _finding(category, severity, scope, subject, employee, metric, observed,
             baseline, deviation, detail, action):
    return validate_finding({
        "category": category, "severity": severity, "scope": scope,
        "subject": subject, "employee": employee, "metric": metric,
        "observed": observed, "baseline": baseline, "deviation": deviation,
        "detail": detail, "action": action,
    })


def pair_punches(events):
    """Pair IN/OUT events in time order, surviving midnight boundaries.

    events: list of (datetime, log_type) sorted by time.
    """
    pairs, extra_ins, orphan_outs = [], 0, 0
    open_in = None
    for moment, log_type in events:
        if log_type == "IN":
            if open_in is None:
                open_in = moment
            else:
                extra_ins += 1
        elif log_type == "OUT":
            if open_in is None:
                orphan_outs += 1
            else:
                pairs.append((open_in, moment))
                open_in = None
    return pairs, {"extra_ins": extra_ins, "orphan_outs": orphan_outs,
                   "unclosed": 1 if open_in is not None else 0}


def run_all(context):
    findings = []
    for _category, check in CHECKS:
        findings.extend(check(context))
    return findings


def check_unpaired_punches(context):
    findings = []
    for row in context.get("punch_issues", []):
        findings.append(_finding(
            "Checkin", "Medium", "Employee", row.get("employee_name") or row["employee"],
            row["employee"], "Unpaired punches",
            f"{row['orphan_outs']} OUT without IN, {row['unclosed']} IN without OUT, {row['extra_ins']} extra IN",
            "Every IN should pair with the next OUT",
            f"{row['orphan_outs'] + row['unclosed'] + row['extra_ins']} unpaired",
            "A day without a matched check-out can drop paid days or overtime.",
            "Review the device log and add an attendance correction for the affected day",
        ))
    return findings


def check_shift_duration_outliers(context):
    findings = []
    threshold = float(context.get("z_threshold") or 3.5)
    min_cohort = int(context.get("min_cohort") or 5)
    for hit in cohort_findings(context.get("duration_observations", []), threshold, min_cohort):
        row = hit["row"]
        deviation = f"robust z={hit['z']:.1f}" if hit["z"] is not None else "zero spread in cohort"
        findings.append(_finding(
            "Checkin", "Medium", "Employee", row.get("employee_name") or row["key"],
            row["key"], "Median shift duration (minutes)",
            f"{row['value']:.0f}", f"cohort median {hit['center']:.0f}",
            deviation, f"{row['days']} paired days",
            "Confirm shift timing and punch pairing with the department supervisor",
        ))
    return findings


def check_punch_trend_outliers(context):
    findings = []
    threshold = float(context.get("z_threshold") or 3.5)
    min_cohort = int(context.get("min_cohort") or 5)
    min_previous = int(context.get("min_previous") or 5)
    for hit in trend_outliers(context.get("punch_trend_observations", []), threshold,
                              min_cohort, min_previous):
        row = hit["row"]
        findings.append(_finding(
            "Checkin", "Medium", "Employee", row.get("employee_name") or row["key"],
            row["key"], "Punches vs previous period",
            f"{row['current']} punches", f"{row['previous']} last period",
            f"{row['change'] * 100:+.0f}% (z={hit['z']:.1f})",
            "Compared with the same-length window immediately before the period.",
            "Verify absence, leave, or device changes before payroll",
        ))
    return findings


def check_present_without_punch(context):
    paired = context.get("paired_days", {})
    cover = context.get("leave_cover", set())
    counts, names = {}, {}
    for row in context.get("attendance_rows", []):
        if row.get("status") not in PRESENT_STATUSES:
            continue
        employee = row["employee"]
        day = str(row.get("attendance_date"))[:10]
        names[employee] = row.get("employee_name") or employee
        if day in paired.get(employee, set()):
            continue
        if f"{employee}|{day}" in cover:
            continue
        counts[employee] = counts.get(employee, 0) + 1
    findings = []
    for employee in sorted(counts):
        findings.append(_finding(
            "Attendance", "Medium", "Employee", names[employee], employee,
            "Present without a paired punch",
            f"{counts[employee]} day(s)", "Present days should have a paired IN/OUT",
            str(counts[employee]),
            "Attendance marks present but the device shows no usable punch, or the punch is unpaired.",
            "Verify the device log or add an attendance correction before payroll",
        ))
    return findings


def check_slip_arithmetic(context):
    tolerance = float(context.get("tolerance") or 0.01)
    earnings = context.get("earning_totals", {})
    deductions = context.get("deduction_totals", {})
    findings = []
    for slip in context.get("slips", []):
        gross = float(slip.get("gross_pay") or 0)
        net = float(slip.get("net_pay") or 0)
        problems = []
        if abs(gross - float(earnings.get(slip["name"], 0))) > tolerance:
            problems.append(f"gross {gross:,.2f} vs components {float(earnings.get(slip['name'], 0)):,.2f}")
        if abs(net - (gross - float(deductions.get(slip["name"], 0)))) > tolerance:
            problems.append(f"net {net:,.2f} vs gross-deductions {gross - float(deductions.get(slip['name'], 0)):,.2f}")
        if not problems:
            continue
        findings.append(_finding(
            "Payroll", "High", "Employee", slip.get("employee_name") or slip["employee"],
            slip["employee"], "Salary slip arithmetic",
            "; ".join(problems), "gross = sum(earnings); net = gross - sum(deductions)",
            "mismatch", f"Draft slip {slip['name']} for {slip.get('start_date')} to {slip.get('end_date')}.",
            "Recompute and reprice the draft before submission",
        ))
    return findings


def check_zero_gross_with_punches(context):
    findings = []
    for slip in context.get("slips", []):
        if float(slip.get("gross_pay") or 0) != 0:
            continue
        punches = context.get("slip_punch_any", {}).get(slip["name"], 0)
        if not punches:
            continue
        findings.append(_finding(
            "Payroll", "High", "Employee", slip.get("employee_name") or slip["employee"],
            slip["employee"], "Zero gross with device punches",
            f"gross 0.00 with {punches} punch day(s)",
            "Punch activity should produce payable days",
            str(punches),
            f"Slip {slip['name']} covers {slip.get('start_date')} to {slip.get('end_date')}.",
            "Reprice the draft after resolving attendance pairing and policy coverage",
        ))
    return findings


def check_duplicate_slips(context):
    groups = {}
    for slip in context.get("slips", []):
        key = (slip["employee"], str(slip.get("start_date")), str(slip.get("end_date")))
        groups.setdefault(key, []).append(slip)
    findings = []
    for (employee, start, end), slips in sorted(groups.items()):
        if len(slips) < 2:
            continue
        names = ", ".join(slip["name"] for slip in slips)
        findings.append(_finding(
            "Payroll", "High", "Employee", slips[0].get("employee_name") or employee,
            employee, "Duplicate active salary slips",
            f"{len(slips)} slips for {start} to {end}", "One active slip per employee and period",
            str(len(slips)),
            f"Slips: {names}.",
            "Cancel the duplicate before submission",
        ))
    return findings


def check_payment_days_out_of_range(context):
    findings = []
    for slip in context.get("slips", []):
        period_days = (slip["end_date"] - slip["start_date"]).days + 1
        payment_days = float(slip.get("payment_days") or 0)
        if 0 <= payment_days <= period_days:
            continue
        findings.append(_finding(
            "Payroll", "High", "Employee", slip.get("employee_name") or slip["employee"],
            slip["employee"], "Payment days outside the period",
            f"{payment_days:g} days", f"period has {period_days} days",
            f"{payment_days - period_days:+g}",
            f"Slip {slip['name']} for {slip.get('start_date')} to {slip.get('end_date')}.",
            "Correct the payment days before submission",
        ))
    return findings


def check_paid_vs_punch_days(context):
    tolerance = float(context.get("day_tolerance") or 1)
    wage_structures = context.get("wage_structures", set())
    paired_days = context.get("slip_paired_days", {})
    period_to = context.get("period_to_date")
    findings = []
    for slip in context.get("slips", []):
        if slip.get("salary_structure") not in wage_structures:
            continue
        if period_to and slip["end_date"] > period_to:
            continue  # only judge periods fully inside the analysed window
        if float(slip.get("gross_pay") or 0) == 0:
            continue
        paid = float(slip.get("payment_days") or 0)
        worked = float(paired_days.get(slip["name"], 0))
        if abs(paid - worked) <= tolerance:
            continue
        findings.append(_finding(
            "Payroll", "High", "Employee", slip.get("employee_name") or slip["employee"],
            slip["employee"], "Paid days vs paired punch days",
            f"{paid:g} paid", f"{worked:g} paired punch days",
            f"{paid - worked:+g}",
            f"Draft slip {slip['name']} for {slip.get('start_date')} to {slip.get('end_date')}; "
            f"device data {context.get('checkin_span') or 'span unknown'}.",
            "Reprice the draft from the paired punch evidence or correct attendance first",
        ))
    return findings


def check_base_outliers(context):
    findings = []
    threshold = float(context.get("z_threshold") or 3.5)
    min_cohort = int(context.get("min_cohort") or 5)
    for hit in cohort_findings(context.get("base_observations", []), threshold, min_cohort):
        row = hit["row"]
        deviation = f"robust z={hit['z']:.1f}" if hit["z"] is not None else "zero spread in cohort"
        findings.append(_finding(
            "Payroll", "Medium", "Employee", row.get("employee_name") or row["key"],
            row["key"], f"Base pay vs {row['cohort']}",
            f"{row['value']:,.0f}", f"structure median {hit['center']:,.0f}",
            deviation, "Compared across employees on the same salary structure.",
            "Confirm the contracted salary with HR and accounts",
        ))
    return findings


def check_leave_balance_negative(context):
    findings = []
    for row in context.get("leave_balances", []):
        balance = float(row.get("allocated") or 0) - float(row.get("used") or 0)
        if balance >= 0:
            continue
        findings.append(_finding(
            "Leave", "High", "Employee", row.get("employee_name") or row["employee"],
            row["employee"], f"Negative {row['leave_type']} balance",
            f"{balance:g} days", "balance = allocated - approved leave",
            f"{balance:g}",
            "Approved leave exceeds the allocation for the overlapping period.",
            "Correct the allocation or the leave application before payroll",
        ))
    return findings


def check_leave_without_allocation(context):
    findings = []
    for row in context.get("leave_without_allocation", []):
        findings.append(_finding(
            "Leave", "Medium", "Employee", row.get("employee_name") or row["employee"],
            row["employee"], f"Leave without allocation: {row['leave_type']}",
            f"{float(row.get('days') or 0):g} day(s) from {row.get('from_date')}",
            "Approved leave should fall inside an allocation",
            "no covering allocation",
            "Approved leave exists without a matching Leave Allocation period.",
            "Create the allocation or correct the leave dates",
        ))
    return findings


def check_missing_tax_slab(context):
    if not context.get("active_slip_count") or context.get("tax_slab_count"):
        return []
    return [_finding(
        "Tax", "Medium", "Company", context.get("company_name") or "", "",
        "Income Tax Slab coverage",
        "No active Income Tax Slab", "Payroll exists for the period",
        "missing",
        "TDS cannot be computed for taxable payroll without a slab.",
        "Create and submit the company's Income Tax Slab",
    )]


def check_employee_without_shift_assignment(context):
    findings = []
    for row in context.get("no_shift_assignment", []):
        findings.append(_finding(
            "Attendance", "High", "Employee", row.get("employee_name") or row["employee"],
            row["employee"], "Shift assignment missing",
            "no active Shift Assignment",
            "Every active employee needs a shift to derive late/absent",
            "missing",
            "Without an assigned shift, device punches cannot be turned into "
            "late/early/absent and this employee's days stay uncounted by rule.",
            "Create a Shift Assignment for this employee with the correct shift and window",
        ))
    return findings


def check_attendance_without_shift_link(context):
    data = context.get("attendance_no_shift") or {}
    total = int(data.get("total") or 0)
    rows = int(data.get("rows") or 0)
    if not total or not rows:
        return []
    pct = rows * 100.0 / total
    return [_finding(
        "Attendance", "Medium", "Company", context.get("company_name") or "", "",
        "Attendance rows not linked to a shift",
        f"{rows:,} of {total:,} rows in the period",
        "Attendance should reference the shift it was counted against",
        f"{pct:.0f}%",
        "Without a shift link, late/early/absent cannot be re-derived or audited from punches.",
        "Link shifts on attendance records (backfill) or enable shift-based auto attendance",
    )]


CHECKS = (
    ("Checkin", check_unpaired_punches),
    ("Checkin", check_shift_duration_outliers),
    ("Checkin", check_punch_trend_outliers),
    ("Attendance", check_present_without_punch),
    ("Attendance", check_employee_without_shift_assignment),
    ("Attendance", check_attendance_without_shift_link),
    ("Payroll", check_slip_arithmetic),
    ("Payroll", check_zero_gross_with_punches),
    ("Payroll", check_duplicate_slips),
    ("Payroll", check_payment_days_out_of_range),
    ("Payroll", check_paid_vs_punch_days),
    ("Payroll", check_base_outliers),
    ("Leave", check_leave_balance_negative),
    ("Leave", check_leave_without_allocation),
    ("Tax", check_missing_tax_slab),
)
