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
    calculate_wage,
    employee_joins_after_period,
    source_gross,
)


WORKER_STRUCTURE = "TCL Factory Daily Wage Worker Structure"
SOURCE_EMPLOYEE_ID_FIELD = "tradex_source_employee_id"
DEFAULT_SOURCE_COMPENSATION_FILE = os.path.expanduser(
    "~/frappe-bench/sync/data/selevo_employee_compensation.json"
)


def configured_components():
    raw = os.getenv("TRADEX_PAYROLL_COMPONENTS_JSON")
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("TRADEX_PAYROLL_COMPONENTS_JSON must be valid JSON") from exc
    if not isinstance(value, dict):
        raise TypeError("TRADEX_PAYROLL_COMPONENTS_JSON must be an object")
    return value


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


def _source_earnings(record: dict[str, Any], gross: Decimal) -> list[dict[str, Any]]:
    components = (record.get("current_compensation") or {}).get("components") or []
    if not components:
        return []
    aliases = {
        "Entertainment Allowance": "Recreation Allowance",
        "Recreation Allowance": "Recreation Allowance",
    }
    amounts: dict[str, Decimal] = {}
    abbreviations = {
        "Basic Salary": "BASIC",
        "House Rent Allowance": "HRA",
        "Medical Allowance": "MED",
        "Conveyance Allowance": "CONV",
        "Recreation Allowance": "RA",
    }
    for component in components:
        name = aliases.get(component.get("name"), component.get("name"))
        if name not in abbreviations:
            continue
        amounts[name] = amounts.get(name, Decimal(0)) + Decimal(str(component.get("amount") or 0)) / 100
    amounts.setdefault("Recreation Allowance", Decimal(0))
    if sum(amounts.values(), Decimal(0)).quantize(Decimal("0.01")) != gross:
        return []
    return [
        {"salary_component": name, "abbr": abbreviations[name], "amount": amount}
        for name, amount in amounts.items()
    ]


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
            "earnings": _source_earnings(record, amount),
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
                    source_record = _source_record_for_employee(source_salary, employee)
                    if source_record is None and not allow_manual_staff_payroll:
                        pending += 1
                        print(f"[WARN] {employee['name']}: staff source salary is missing")
                        continue
                    base = source_record["gross"] if source_record is not None else Decimal(str(assignment.base or 0))
                    if base <= 0:
                        pending += 1
                        print(f"[WARN] {employee['name']}: staff salary amount is empty")
                        continue
                    earnings = source_record["earnings"] if source_record and source_record["earnings"] else calculate_wage(base, configured_components())["earnings"]
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
                frappe.db.rollback()
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
