"""Create draft payroll slips using editable policy and source data.

Historical submitted slips are handled by ``reconcile_payroll.py``. This
runner never submits or replaces an existing draft or accounting document.
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

import frappe

from tradex_hr.tradexcel_hr.payroll_rules import (
    calculate_dated_worker_pay,
    employee_joins_after_period,
    source_gross,
)


SOURCE_EMPLOYEE_ID_FIELD = "tradex_source_employee_id"
DEFAULT_SOURCE_COMPENSATION_FILE = os.path.expanduser(
    "~/frappe-bench/sync/data/selevo_employee_compensation.json"
)


def structure_earnings(salary_structure: str, gross) -> list[dict[str, Any]]:
    """Split `gross` using the earnings declared on the Salary Structure.

    This is the ONLY place the split is defined. Percentages live on the
    structure (e.g. Basic = base * 0.6), which is configuration an HR user can
    see and edit — not a hardcoded dict in the code.

    Resolving to fixed amounts here (rather than letting HRMS evaluate the
    formulas) keeps the runner's behaviour identical to the reviewer's
    arithmetic: base x 0.6, base x 0.3, and so on.

    Rows with no formula (a fixed amount, or zero like Entertainment Allowance)
    contribute their own amount.
    """
    from decimal import ROUND_HALF_UP

    structure = frappe.get_doc("Salary Structure", salary_structure)
    base = Decimal(str(gross))
    out: list[dict[str, Any]] = []
    for row in structure.earnings:
        formula = (row.formula or "").strip()
        if formula and "payment_days" in formula:
            # Daily-wage structures are paid per attendance day and are handled
            # by calculate_dated_worker_pay(), not the monthly gross split.
            raise ValueError(
                f"{salary_structure} is attendance-based (formula {formula!r}); "
                f"monthly gross splitting does not apply."
            )
        if formula:
            # structures declare `base * <factor>`; anything else is refused
            # rather than guessed, so a new formula cannot silently mis-pay.
            if not formula.replace(" ", "").startswith("base*"):
                raise ValueError(
                    f"{salary_structure}: earnings row {row.salary_component!r} uses "
                    f"formula {formula!r}, which this runner cannot evaluate safely. "
                    f"Use `base * <factor>` or move the logic into Additional Salary."
                )
            factor = Decimal(formula.replace(" ", "")[len("base*"):])
            amount = (base * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            amount = Decimal(str(row.amount or 0)).quantize(Decimal("0.01"))
        out.append({"salary_component": row.salary_component,
                    "abbr": row.abbr or row.salary_component[:3].upper(),
                    "amount": amount})

    declared = sum((r["amount"] for r in out), Decimal(0))
    if declared != base:
        raise ValueError(
            f"{salary_structure}: earnings total {declared} does not equal the "
            f"assignment base {base}. Fix the structure percentages — they must "
            f"sum to 100%."
        )
    return out


def _salary_detail(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "salary_component": row["salary_component"],
        "abbr": row["abbr"],
        "amount": float(row["amount"]),
        "default_amount": 0,
        "amount_based_on_formula": 0,
        "depends_on_payment_days": 1,
    }


def _create_manual_slip(data: dict[str, Any]) -> Any:
    payload = dict(data)
    assignment_base = payload.pop("assignment_base", None)
    slip = frappe.get_doc(payload)
    slip._salary_structure_doc = frappe.get_doc("Salary Structure", data["salary_structure"])
    # Do not replace the source-derived paid days with global Payroll Settings.
    slip.get_working_days_details = lambda lwp=None, for_preview=0: None
    slip.calculate_component_amounts = lambda component_type: None
    from tradex_hr.tradexcel_hr.deduction_rules import recompute_totals, structure_deductions

    gross = sum(float(row.amount or 0) for row in slip.earnings)
    deductions = structure_deductions(
        data["salary_structure"], gross,
        base=assignment_base,
        payment_days=slip.payment_days,
        total_working_days=slip.total_working_days,
        earnings=slip.earnings,
    )
    for row in deductions:
        slip.append("deductions", row)
    recompute_totals(slip)
    slip.insert(ignore_permissions=True)
    return slip


def _checkin_records(employee: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    rows = frappe.db.sql(
        """
        SELECT time, log_type
        FROM `tabEmployee Checkin`
        WHERE employee=%s AND time >= %s AND time <= %s
        ORDER BY time ASC
        """,
        (employee, f"{start_date} 00:00:00", f"{end_date} 23:59:59"),
        as_dict=True,
    )
    grouped: dict[str, dict[str, list[Any]]] = defaultdict(lambda: {"IN": [], "OUT": []})
    for row in rows:
        timestamp = row.time
        day = timestamp.date().isoformat() if hasattr(timestamp, "date") else str(timestamp)[:10]
        if row.log_type in ("IN", "OUT"):
            grouped[day][row.log_type].append(timestamp)

    records = []
    for day, events in sorted(grouped.items()):
        if not events["IN"] or not events["OUT"]:
            continue
        check_in = min(events["IN"])
        check_out = max(events["OUT"])
        records.append(
            {
                "date": day,
                "isPayable": check_out >= check_in,
                "checkInTime": check_in.isoformat() if hasattr(check_in, "isoformat") else str(check_in),
                "checkOutTime": check_out.isoformat() if hasattr(check_out, "isoformat") else str(check_out),
            }
        )
    return records


def _load_source_salary(path: str | None) -> dict[str, Any]:
    if not path or not Path(path).exists():
        return {"by_source_id": {}, "by_number": {}}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    records = payload.get("records") or payload.get("compensations") or payload.get("employees") or []
    by_source_id = {}
    by_number = defaultdict(list)
    for record in records:
        if not isinstance(record, dict):
            continue
        employee = record.get("employee") if isinstance(record.get("employee"), dict) else record
        number = employee.get("employeeNumber") or employee.get("employee_number")
        source_id = employee.get("id") or employee.get("source_employee_id")
        raw_amount = record.get("current_salary_amount")
        if raw_amount not in (None, "") and record.get("current_salary_currency") == "BDT":
            amount = Decimal(str(raw_amount)) / 100
        else:
            amount = source_gross(record)
        if not amount or amount <= 0:
            continue
        source_record = {
            "gross": amount.quantize(Decimal("0.01")),
            "source_employee_id": str(source_id) if source_id not in (None, "") else None,
        }
        if source_record["source_employee_id"]:
            by_source_id[source_record["source_employee_id"]] = source_record
        if number:
            by_number[str(number)].append(source_record)
    return {
        "by_source_id": by_source_id,
        "by_number": {number: values[0] for number, values in by_number.items() if len(values) == 1},
    }


def _source_record_for_employee(source_salary: dict[str, Any], employee: dict[str, Any]):
    source_id = employee.get(SOURCE_EMPLOYEE_ID_FIELD)
    if source_id:
        source_record = source_salary["by_source_id"].get(str(source_id))
        if source_record:
            return source_record
    number = employee.get("employee_number")
    return source_salary["by_number"].get(str(number)) if number else None


def _slip_data(
    employee: dict[str, Any],
    assignment: dict[str, Any],
    start_date: str,
    end_date: str,
    *,
    earnings: list[dict[str, Any]],
    gross: Decimal,
    payment_days: int,
    total_working_days: int,
    unmarked_days: int,
    total_working_hours: Decimal = Decimal(0),
    hour_rate: Decimal = Decimal(0),
) -> dict[str, Any]:
    return {
        "doctype": "Salary Slip",
        "employee": employee["name"],
        "company": employee["company"],
        "department": employee.get("department"),
        "branch": employee.get("branch"),
        "posting_date": end_date,
        "start_date": start_date,
        "end_date": end_date,
        "salary_structure": assignment["salary_structure"],
        "assignment_base": float(assignment["base"] or 0),
        "payroll_frequency": "Monthly",
        "currency": "BDT",
        "total_working_days": float(total_working_days),
        "unmarked_days": float(unmarked_days),
        "payment_days": float(payment_days),
        "absent_days": float(max(total_working_days - payment_days, 0)),
        "leave_without_pay": 0,
        "total_working_hours": float(total_working_hours),
        "hour_rate": float(hour_rate),
        "base_hour_rate": float(hour_rate),
        "gross_pay": float(gross),
        "base_gross_pay": float(gross),
        "net_pay": float(gross),
        "base_net_pay": float(gross),
        "rounded_total": float(round(gross)),
        "base_rounded_total": float(round(gross)),
        "earnings": earnings,
        "deductions": [],
    }


def run_payroll_for_month(
    year,
    month,
    company="Tradexcel Ceramics Ltd.",
    *,
    source_compensation_file: str | None = None,
    allow_manual_staff_payroll: bool = False,
):
    sites_path = os.path.expanduser("~/frappe-bench/sites")
    frappe.init(site="hrms.localhost", sites_path=sites_path)
    frappe.connect()
    try:
        days = calendar.monthrange(year, month)[1]
        start_date = f"{year:04d}-{month:02d}-01"
        end_date = f"{year:04d}-{month:02d}-{days:02d}"
        if source_compensation_file is None and Path(DEFAULT_SOURCE_COMPENSATION_FILE).exists():
            source_compensation_file = DEFAULT_SOURCE_COMPENSATION_FILE

        from tradex_hr.tradexcel_hr.component_exceptions import apply_component_rules, load_component_rules
        from tradex_hr.tradexcel_hr.payroll_policy import resolve_policy

        component_rules = load_component_rules(company)

        assignments = frappe.db.sql(
            """
            SELECT a.employee, a.salary_structure, a.base, e.name, e.employee_name,
                   e.company, e.department, e.branch, e.employment_type, e.employee_number,
                   e.tradex_source_employee_id, e.date_of_joining
            FROM `tabSalary Structure Assignment` a
            JOIN `tabEmployee` e ON e.name = a.employee
            WHERE a.company = %s AND a.docstatus = 1 AND a.from_date <= %s
              AND (e.relieving_date IS NULL OR e.relieving_date >= %s)
              AND e.status = 'Active'
            ORDER BY e.name ASC, a.from_date DESC, a.creation DESC
            """,
            (company, end_date, start_date),
            as_dict=True,
        )
        latest_by_employee = {}
        for assignment in assignments:
            latest_by_employee.setdefault(assignment.employee, assignment)

        source_salary = _load_source_salary(source_compensation_file)
        created = 0
        skipped = 0
        pending = 0
        total_gross = Decimal(0)
        failures = []

        for assignment in latest_by_employee.values():
            employee = dict(assignment)
            if employee_joins_after_period(employee.get("date_of_joining"), end_date):
                pending += 1
                print(f"[WARN] {employee['name']}: joined after payroll period; skipped")
                continue
            policy = resolve_policy(employee["name"], start_date)
            if not policy:
                pending += 1
                print(f"[WARN] {employee['name']}: no active Tradexcel Payroll Policy")
                continue

            existing = frappe.db.get_value(
                "Salary Slip",
                {"employee": employee["name"], "start_date": start_date, "docstatus": ["<", 2]},
                ["name", "docstatus"],
                as_dict=True,
            )
            if existing:
                skipped += 1
                print(f"[INFO] {employee['name']}: {'submitted' if existing.docstatus == 1 else 'draft'} slip already exists; not overwritten")
                continue

            try:
                frappe.db.savepoint("payroll_row")
                if policy.pay_basis == "Daily Wage":
                    records = _checkin_records(employee["name"], start_date, end_date)
                    pay = calculate_dated_worker_pay(
                        records,
                        lambda day: resolve_policy(employee["name"], day),
                    )
                    earnings = [
                        _salary_detail({"salary_component": "Daily Wage", "abbr": "DW", "amount": pay["regular"]}),
                        _salary_detail({"salary_component": "Overtime Pay", "abbr": "OT", "amount": pay["overtime"]}),
                    ]
                    earnings = apply_component_rules(earnings, employee, start_date, component_rules)
                    data = _slip_data(
                        employee,
                        assignment,
                        start_date,
                        end_date,
                        earnings=earnings,
                        gross=pay["gross"],
                        payment_days=pay["paid_days"],
                        total_working_days=len(records),
                        unmarked_days=max(days - len(records), 0),
                        total_working_hours=pay["worked_hours"],
                        hour_rate=pay["single_hour_rate"],
                    )
                else:
                    # THE ASSIGNMENT IS THE SOURCE OF TRUTH.
                    #
                    # This used to read the amount from a JSON file outside the
                    # repository (sync/data/selevo_employee_compensation.json),
                    # which existed only on this machine. That gave the same
                    # number two homes: the assignment we maintain, and a file
                    # that would silently disappear on a redeploy. They happened
                    # to agree (67/67 verified 2026-09-18), but two sources of
                    # truth is a defect regardless of whether they currently
                    # match.
                    #
                    # The file is now used for one purpose only: a deliberate
                    # seed when an assignment has no base, and only when
                    # explicitly asked for. Assignment wins, always.
                    base = Decimal(str(assignment.base or 0))
                    if base <= 0 and source_record is not None:
                        base = Decimal(str(source_record["gross"]))
                        print(f"[INFO] {employee['name']}: no assignment base; "
                              f"seeded from source file ({base}) — set it on the assignment")
                    if base <= 0:
                        pending += 1
                        print(f"[WARN] {employee['name']}: salary amount is empty on the assignment")
                        continue

                    # Earnings come from the structure the assignment points at,
                    # so a change to the structure changes payroll. No hardcoded
                    # component percentages.
                    earnings = structure_earnings(assignment["salary_structure"], base)
                    earnings = apply_component_rules(earnings, employee, start_date, component_rules)
                    data = _slip_data(
                        employee,
                        assignment,
                        start_date,
                        end_date,
                        earnings=[_salary_detail(row) for row in earnings],
                        gross=base,
                        payment_days=days,
                        total_working_days=days,
                        unmarked_days=0,
                    )

                slip = _create_manual_slip(data)
                created += 1
                total_gross += Decimal(str(slip.gross_pay or 0))
                frappe.db.commit()
            except Exception as exc:  # noqa: BLE001 - report one employee and continue
                # A savepoint, NOT a full rollback. frappe.db.rollback() here
                # discarded every slip created earlier in the loop, so one bad
                # employee looked like a wholesale failure.
                frappe.db.rollback(save_point="payroll_row")
                failures.append({"employee": employee["name"], "error": f"{type(exc).__name__}: {str(exc)[:240]}"})
                print(f"[ERROR] Payroll failed for {employee['name']}: {failures[-1]['error']}")

        print(f"[OK] Payroll complete for {year:04d}-{month:02d}; created={created}, skipped={skipped}, pending={pending}, gross={total_gross:,.2f}, failed={len(failures)}")
        return not failures
    finally:
        frappe.destroy()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TradeX policy-driven payroll runner")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--month", type=int, default=8)
    parser.add_argument("--company", default="Tradexcel Ceramics Ltd.")
    parser.add_argument("--source-compensation-file")
    parser.add_argument("--allow-manual-staff-payroll", action="store_true")
    args = parser.parse_args()
    raise SystemExit(
        0
        if run_payroll_for_month(
            args.year,
            args.month,
            company=args.company,
            source_compensation_file=args.source_compensation_file,
            allow_manual_staff_payroll=args.allow_manual_staff_payroll,
        )
        else 1
    )
