"""Scoped salary-component exceptions: pure matcher plus DB-aware loader."""

from __future__ import annotations

import frappe
from frappe.utils import getdate


class ComponentRuleConflict(ValueError):
    """Two equally specific rules disagree about one component."""

    def __init__(self, component, names):
        self.component = component
        self.names = sorted(names)
        super().__init__(f"Conflicting {component} rules: {', '.join(self.names)}")


def _in_window(rule, day):
    if rule.get("effective_from") and getdate(rule["effective_from"]) > day:
        return False
    if rule.get("effective_to") and getdate(rule["effective_to"]) < day:
        return False
    return True


def scope_match(employee, rule):
    """True when the employee falls inside every scope dimension the rule sets."""
    if rule.get("company") and rule["company"] != employee.get("company"):
        return False
    if rule.get("employee") and rule["employee"] != employee.get("name"):
        return False
    if rule.get("branch_scope") and employee.get("branch") not in rule["branch_scope"]:
        return False
    if rule.get("department_scope") and employee.get("department") not in rule["department_scope"]:
        return False
    if rule.get("designation") and rule["designation"] != employee.get("designation"):
        return False
    return True


def _rank(rule):
    # Specificity follows the org hierarchy: employee > department/designation > branch.
    dimension_weight = 0
    if rule.get("department_scope"):
        dimension_weight += 10
    if rule.get("designation"):
        dimension_weight += 10
    if rule.get("branch_scope"):
        dimension_weight += 1
    return (
        1 if rule.get("employee") else 0,
        dimension_weight,
        -len(rule.get("branch_scope") or []) - len(rule.get("department_scope") or []),
    )


def resolve_component(employee, day, rules, component):
    day = getdate(day)
    matches = [
        rule for rule in rules
        if str(rule.get("salary_component") or "").casefold() == component.casefold()
        and _in_window(rule, day)
        and scope_match(employee, rule)
    ]
    if not matches:
        return None
    top_rank = max(_rank(rule) for rule in matches)
    top = [rule for rule in matches if _rank(rule) == top_rank]
    decisions = {(rule.get("component_action"), str(rule.get("component_amount") or "")) for rule in top}
    if len(decisions) > 1:
        raise ComponentRuleConflict(component, [rule["name"] for rule in top])
    return top[0]


def apply_component_rules(earnings, employee, day, rules):
    """Filter or override component rows. Returns a new list; never mutates input."""
    if not rules:
        return earnings
    kept = []
    for row in earnings:
        rule = resolve_component(employee, day, rules, str(row.get("salary_component") or ""))
        if rule is None:
            kept.append(row)
            continue
        action = rule.get("component_action")
        if action == "Exclude":
            continue
        if action == "Override Amount":
            kept.append({**row, "amount": float(rule.get("component_amount") or 0)})
        else:
            kept.append(row)
    return kept


def expand_scope(value, descendants):
    if not value:
        return None
    return [value, *sorted(descendants.get(value, set()) - {value})]


def build_rule(source, branch_descendants, department_descendants, include_children=True):
    rule = {
        "name": source.get("name"),
        "company": source.get("company"),
        "employee": source.get("employee"),
        "designation": source.get("designation"),
        "salary_component": source.get("salary_component"),
        "component_action": source.get("component_action"),
        "component_amount": source.get("component_amount"),
        "effective_from": source.get("effective_from"),
        "effective_to": source.get("effective_to"),
    }
    if include_children:
        rule["branch_scope"] = expand_scope(source.get("branch"), branch_descendants)
        rule["department_scope"] = expand_scope(source.get("department"), department_descendants)
    else:
        rule["branch_scope"] = [source.get("branch")] if source.get("branch") else None
        rule["department_scope"] = [source.get("department")] if source.get("department") else None
    return rule


def branch_scope_map():
    rows = frappe.get_all("Branch", fields=["name", "parent_branch"])
    children = {}
    for row in rows:
        children.setdefault(row.parent_branch, []).append(row.name)

    def descendants(name, seen):
        found = set()
        for child in children.get(name, []):
            if child in seen:
                continue
            seen.add(child)
            found.add(child)
            found |= descendants(child, seen)
        return found

    return {row.name: descendants(row.name, {row.name}) for row in rows}


def department_scope_map():
    rows = frappe.get_all("Department", fields=["name", "lft", "rgt"])
    return {
        row.name: {other.name for other in rows if other.lft > row.lft and other.rgt < row.rgt}
        for row in rows
    }


def load_component_rules(company):
    rows = frappe.get_all(
        "Tradexcel Policy Exception",
        filters={"docstatus": 1, "company": company, "exception_type": "Component"},
        fields=["name", "company", "employee", "designation", "salary_component",
                "component_action", "component_amount", "effective_from", "effective_to",
                "branch", "department", "include_child_scope"],
    )
    if not rows:
        return []
    branch_map, department_map = branch_scope_map(), department_scope_map()
    return [
        build_rule(row, branch_map, department_map,
                   include_children=bool(row.get("include_child_scope", 1)))
        for row in rows
    ]


def apply_to_salary_slip(doc, method=None):
    """Doc event: keep excluded components off every salary slip, not just runner ones."""
    if not doc.employee or not doc.company or not doc.earnings:
        return
    rules = load_component_rules(doc.company)
    if not rules:
        return
    employee = frappe.db.get_value(
        "Employee", doc.employee,
        ["name", "company", "branch", "department", "designation"], as_dict=True,
    )
    if not employee:
        return
    day = doc.start_date or frappe.utils.today()
    original = [(row.salary_component, round(float(row.amount or 0), 2)) for row in doc.earnings]
    kept = apply_component_rules(
        [{"salary_component": row.salary_component, "abbr": row.abbr, "amount": row.amount}
         for row in doc.earnings],
        employee, day, rules,
    )
    updated = [(row["salary_component"], round(float(row.get("amount") or 0), 2)) for row in kept]
    if updated == original:
        return
    doc.earnings = []
    for row in kept:
        doc.append("earnings", row)
    from tradex_hr.tradexcel_hr.deduction_rules import recompute_totals

    recompute_totals(doc)
