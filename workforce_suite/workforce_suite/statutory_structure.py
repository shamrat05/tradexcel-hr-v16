"""Pure prescribed table geometry shared by bilingual HTML and Word renderers."""
from functools import lru_cache
from pathlib import Path
import json


@lru_cache(maxsize=1)
def definitions():
    data = json.loads(Path(__file__).with_name("statutory_form_specs.json").read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in data["entries"]}


def matrices_for(code, section):
    return [m for m in definitions().get(code, {}).get("matrices", []) if m["section_key"] == section]


def matrix_keys(matrices):
    return {key for matrix in matrices for row in matrix["cells"] for key in row}


def validate_evidence_values(source, values):
    """Validate explicit values only: blank/unresolved never becomes zero."""
    from decimal import Decimal, InvalidOperation
    for key, kind in source.get("value_types", {}).items():
        value = values.get(key)
        if value in (None, "") or kind == "text":
            continue
        if kind == "date":
            from datetime import date
            try:
                date.fromisoformat(str(value))
            except ValueError:
                raise ValueError(f"{key} requires an ISO evidence date") from None
            continue
        try:
            number = Decimal(str(value))
        except InvalidOperation:
            raise ValueError(f"{key} requires a numeric evidenced value") from None
        if not number.is_finite() or (kind != "signed_decimal" and number < 0):
            raise ValueError(f"{key} requires a finite non-negative evidenced value")
        if kind == "integer" and number != number.to_integral_value():
            raise ValueError(f"{key} requires a whole count")
    for first, last in (("history_joined", "history_left"), ("service_leave_from", "service_leave_to"), ("withdrawal_date", "withdrawal_effective_date")):
        if values.get(first) not in (None, "") and values.get(last) not in (None, ""):
            from datetime import date
            beginning, ending = date.fromisoformat(str(values[first])), date.fromisoformat(str(values[last]))
            if ending < beginning or (first == "withdrawal_date" and not 1 <= (ending-beginning).days <= 7):
                raise ValueError(f"{last} conflicts with the source chronology")
    for total in source.get("totals", []):
        keys = [total["total"]] + total["parts"]
        if all(values.get(key) not in (None, "") for key in keys):
            if Decimal(str(values[keys[0]])) != sum((Decimal(str(values[k])) for k in keys[1:]), Decimal(0)):
                raise ValueError(f"{keys[0]} does not reconcile with its evidenced parts")


def repeatable_for(code, section=None):
    return [t for t in definitions().get(code, {}).get("repeatable_tables", [])
            if section is None or t["section_key"] == section]


def repeated_keys(code):
    return {key for table in repeatable_for(code) for key in table["keys"]}


def evidence_rows(entries, code):
    """Project native reviewed cells into source-defined tables with stable rows."""
    values, tables = {}, {}
    known = repeated_keys(code)
    for entry in entries:
        key = entry.field_key
        row = int(entry.get("row_number") or 0)
        value = ("Not Applicable — " + entry.applicability_note
                 if entry.get("value_status") == "Not Applicable" else entry.field_value)
        if key in known:
            table = next(t for t in repeatable_for(code) if key in t["keys"])
            tables.setdefault(table["id"], {}).setdefault(row or 1, {})[key] = value
        else:
            values[key] = value
    values["_history"] = {key: [rows[i] for i in sorted(rows)] for key, rows in tables.items()}
    for records in values["_history"].values():
        records.sort(key=lambda row: next((str(row[key]) for key in ("history_joined", "wage_effective", "service_leave_from", "conduct_date", "certificate_date") if row.get(key)), ""))
    return values


def history_pages(table, rows):
    """Preserve prescribed service-book page capacity without inventing entries."""
    size = table.get("rows_per_page", max(1, len(rows)))
    count = max(table.get("minimum_pages", 1), (len(rows) + size - 1) // size)
    pages = [rows[i*size:(i+1)*size] for i in range(count)]
    if table.get("minimum_pages", 1) > 1:
        pages = [page + [{} for _ in range(size-len(page))] for page in pages]
    return pages


def financial_appendices(rows, language):
    result=[]
    definitions=[('_rate_rows','Reviewed historical overtime rates','পর্যালোচিত ঐতিহাসিক অতিরিক্ত কাজের হার',
                  ['worker','from','to','hours','rate','amount','reference'],
                  ['Worker','From','To','Approved hours','Historical rate','Evidenced amount','Source reference'],
                  ['শ্রমিক','হইতে','পর্যন্ত','অনুমোদিত ঘণ্টা','ঐতিহাসিক হার','প্রমাণিত অর্থ','উৎস রেফারেন্স']),
                 ('_payment_rows','Payment and acknowledgement evidence','পরিশোধ ও প্রাপ্তিস্বীকারের প্রমাণ',
                  ['worker','state','date','amount','reference'],
                  ['Worker','Evidence state','Evidence date','Covered amount','Reference'],
                  ['শ্রমিক','প্রমাণের অবস্থা','প্রমাণের তারিখ','প্রমাণিত অর্থ','রেফারেন্স'])]
    states={'Payment Instructed':'পরিশোধের নির্দেশ','Payment Reconciled':'পরিশোধের সমন্বয়',
            'Worker Payment Evidenced':'শ্রমিককে পরিশোধ প্রমাণিত','Worker Acknowledgement':'শ্রমিকের প্রাপ্তিস্বীকার'}
    for key,en,bn,keys,enlabels,bnlabels in definitions:
        data=[dict(entry) for row in rows for entry in row.get(key,[])]
        if language=='bn':
            for entry in data:
                if 'state' in entry:entry['state']=states.get(entry['state'],entry['state'])
        if data:result.append((bn if language=='bn' else en,keys,bnlabels if language=='bn' else enlabels,data))
    return result
