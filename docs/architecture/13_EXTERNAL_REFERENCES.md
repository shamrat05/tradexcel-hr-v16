# 13 — External references and verification register

This file records the external sources that materially influenced the architecture.
It is a **verification starting point**, not permission to hardcode legal values.

## Bangladesh legal / regulatory sources

### Personal Data Protection Act, 2026

Official Laws of Bangladesh:

- https://bdlaws.minlaw.gov.bd/act-print-1692.html

Relevant current provisions inspected for this architecture include:

- section 2 definitions: biometric data; personal data; sensitive personal data;
  sensitive data includes biometric data and moment-to-moment real-time
  geolocation;
- section 15 accountability/transparency;
- section 16 confidentiality/purpose;
- section 17 security safeguards;
- section 18 retention;
- section 20 breach response.

The Act is Act No. 63 of 2026 and the official text records **10 April 2026**.

Engineering consequence: face images/matching and active GPS location are not
ordinary UI metadata. They require purpose, access, security, retention and
current legal/compliance review.

### Bangladesh Labour Act / 2026 amendment

Official / government sources:

- Bangladesh Labour Act, 2006:
  https://bdlaws.minlaw.gov.bd/act-print-952.html
- Bangladesh Labour (Amendment) Act, 2026:
  https://bdlaws.minlaw.gov.bd/act-print-1672.html
- Department of Inspection for Factories and Establishments law index:
  https://dife.gov.bd/pages/laws
- Ministry of Labour and Employment legislative information:
  https://mole.gov.bd/pages/legislative-informations

Useful secondary consolidation index:

- Bangladesh Employers' Federation Acts & Policies:
  https://bef.org.bd/acts-policies/

The research reviewed current provisions/materials concerning working time,
night-shift treatment, overtime, wage timing/deductions and related labour
controls. The **current authoritative Bangla legal text/Gazette and actual
applicability to the establishment/worker** must be checked before a ruleset is
approved.

Do not copy one section number/rate into permanent code and assume it applies to
every company or population.

### Income tax

National Board of Revenue:

- Income Tax Paripatra:
  https://nbr.gov.bd/taxtypes/income-tax/income-tax-paripatra/eng
- Publications:
  https://nbr.gov.bd/publications/income-tax/60

At the time of this architecture audit, NBR lists **Income Tax Paripatra
2026–2027** and **Income Tax Nirdeshika 2026–2027**.

Engineering consequence: employment-income tax must be fiscal-year/version aware
and approved from current NBR material; no stale tax table may silently roll
forward.

## Frappe / HRMS v16 upstream sources

Agents should inspect the **installed version** first. Upstream source links are
useful for design intent but do not replace installed-version verification.

Repositories:

- Frappe: https://github.com/frappe/frappe
- ERPNext: https://github.com/frappe/erpnext
- Frappe HRMS: https://github.com/frappe/hrms

Version-16 capabilities specifically inspected during this audit include:

### Navigation

Frappe v16 Workspace Sidebar implementation and DocTypes. The framework already
owns persistent sidebar behavior; Tradexcel should prefer sidebar fixtures over a
parallel DOM rail.

### Shift / Checkin

HRMS v16 Employee Checkin and Shift Assignment logic contain:

- resolved shift;
- shift start/end;
- actual shift start/end windows;
- overnight/cross-midnight handling;
- overtime type linkage.

Inspect current files under:

- hrms/hr/doctype/employee_checkin/
- hrms/hr/doctype/shift_assignment/
- hrms/hr/doctype/shift_type/

### Overtime

Current v16 source includes:

- Overtime Type
- Overtime Slip
- Overtime Details
- Shift Type overtime settings
- Attendance overtime fields

Inspect before retaining custom overtime calculation.

### Payroll corrections

Current v16 source includes:

- hrms/payroll/doctype/payroll_correction/
- hrms/payroll/doctype/arrear/
- hrms/payroll/doctype/payroll_entry/
- hrms/payroll/doctype/salary_slip/

Use native Payroll Correction / Arrear where semantics match rather than
inventing another historical-adjustment ledger.

## Project research report

The full project deep-research report is titled:

**Error-Safe HRMS and Payroll for Bangladesh: Practical Failure Modes, Controls,
and Implementation Blueprint**

It supplied the framework-neutral failure register, statutory-control concept,
exception-first design, validation/reconciliation boundaries, low-literacy UX
patterns and test pyramid used by this handbook.

The repo-specific architecture in this directory adds the v16-native capability
map, actual-code critique, mobile/field-duty/face privacy implications and
chunk-by-chunk implementation plan.

## Source-use rule for agents

When a rule may affect money, employee rights, sensitive data or statutory
compliance:

1. identify the applicable company/establishment/population;
2. fetch the current authoritative source;
3. record the exact source/reference/effective date;
4. obtain required business/compliance/legal/accounting review;
5. version the configuration;
6. add boundary fixtures;
7. never retroactively change the meaning of a rule already used in submitted
   payroll.

A link in this file is evidence of what was reviewed, not automatic legal
applicability.
