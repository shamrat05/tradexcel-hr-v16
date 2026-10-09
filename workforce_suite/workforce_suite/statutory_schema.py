"""Protected, non-executable source schema and print-data integrity checks.

Presentation can change; source field identity cannot. These checks do not
certify a source as current law or turn a draft into an approved filing.
"""
from decimal import Decimal


def validate_schema(source, columns):
    expected = {column["field_key"] for column in source["columns"]}
    actual = [column.get("field_key") if isinstance(column, dict)
              else column.field_key for column in columns]
    if len(actual) != len(set(actual)):
        raise ValueError("Source fields cannot be duplicated")
    if set(actual) != expected:
        missing = sorted(expected - set(actual))
        extra = sorted(set(actual) - expected)
        raise ValueError(f"Preserve the protected source fields. Missing: {missing}; unknown: {extra}")
    return expected


def money(value):
    return Decimal(str(value or 0))


def reconcile_wages(earnings, gross, deductions, net, precision=2, loan_repayment=0):
    """Verify native amounts; never allocate or manufacture wage money."""
    tolerance = Decimal(1).scaleb(-precision)
    if abs(sum((money(x) for x in earnings), Decimal(0)) - money(gross)) > tolerance:
        raise ValueError("Salary Slip earnings do not reconcile with gross pay")
    if abs(money(gross) - money(deductions) - money(loan_repayment) - money(net)) > tolerance:
        raise ValueError("Salary Slip gross, deductions and net pay do not reconcile")


def missing_findings(source, rows):
    findings = []
    if not rows:
        return [{"code": "NO_RECORDS", "message": "No authorized source records match this scope."}]
    # Blank signature boxes are intentional in unsigned working copies.
    optional = {c["field_key"] for c in source["columns"]
                if c.get("required_value") is False}
    for index, row in enumerate(rows, 1):
        for column in source["columns"]:
            key = column["field_key"]
            # Form 40's collection date is conditional: an advance may be
            # reviewed before its first repayment. Actual repayment rows mark
            # the field as required in the manual adapter.
            if source.get("id") == "form_40" and key == "requital_date" and not row.get("_requital_required"):
                continue
            if key not in optional and row.get(key) in (None, ""):
                findings.append({"code": "MISSING_VALUE", "row": index,
                                 "field": key, "message": column["label_en"]})
    return findings
