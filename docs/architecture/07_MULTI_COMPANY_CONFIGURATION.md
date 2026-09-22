# 07 — Multi-company and diverse-environment configuration

## Goal

Tradexcel HR must work for a factory, office, footwear company, service business,
multi-site employer, or future company without rewriting payroll code.

The architecture separates:

~~~text
native HRMS master data
+
company operating policy
+
jurisdiction/statutory profile
+
employee-effective assignment
+
exception/override
~~~

## Configuration hierarchy

Suggested precedence for a setting only when the setting is designed to inherit:

~~~text
jurisdiction default
  -> legal/sector profile
    -> company
      -> branch/site
        -> department/designation
          -> employee-specific approved override
~~~

Precedence must be deterministic, documented and tested. Not every field should
inherit through every level.

## Never infer legal regime from geography alone

Examples of distinct profiles may include:

- Bangladesh general Labour Act regime;
- EPZ-specific regime;
- sector-specific wage order;
- contractual/non-worker rules;
- company benefit scheme layered above statutory baseline.

Legal applicability must be explicit and reviewed.

## Company profile

A Company should resolve to an approved profile containing at least:

~~~yaml
company:
default_currency:
timezone:
legal_regime:
establishment_types:
pay_cycle:
default_payment_methods:
default_holiday_policy:
attendance_model:
tax_profile:
statutory_profile:
rounding_policy:
financial_accounts_profile:
~~~

Avoid storing the same semantic value in many unrelated custom fields.

## Attendance models

Support company/site configuration such as:

- no attendance-dependent payroll;
- office shift auto-attendance;
- factory biometric shift attendance;
- hybrid mobile/office;
- field-duty attendance;
- mixed populations.

An office company should not need biometric-device setup.

## Pay models

Do not equate worker/staff with pay method.

Supported pay basis is explicit and can coexist inside one company.

Examples:

~~~text
Worker A      MONTHLY
Worker B      DAILY
Supervisor C  MONTHLY
Field staff D MONTHLY + approved allowance
Technician E  HOURLY (only after implementation)
~~~

## Policy creation UX

Low-skill administrators should use guided setup rather than editing raw formulas.

Wizard pattern:

1. choose company/population;
2. choose pay basis;
3. choose native salary structure;
4. enter rate/base and effective date;
5. show derived component preview;
6. show statutory/compliance checks;
7. show impacted employees;
8. submit for approval.

The wizard writes canonical native/config records.

## Defaults vs inference

Safe default:

> Company X normally uses Holiday List Y. Preselect it for a new employee.

Unsafe inference:

> Department name contains Factory, therefore employee is daily wage.

Defaults are suggestions. Financial classification requires explicit saved state.

## Policy versioning

When a money-driving rule changes, prefer a new effective version rather than
editing past meaning.

Example:

~~~text
TCL Factory Worker Policy v3
effective 2026-01-01 .. 2026-09-30

TCL Factory Worker Policy v4
effective 2026-10-01 ..
~~~

Payroll snapshots/reference records identify the version used.

## Rounding

Rounding is policy, not implementation trivia.

Define:

- currency precision;
- per-component rounding;
- OT duration rounding if lawful/approved;
- final net rounding;
- bank file precision;
- reconciliation tolerance.

One central policy must be used consistently.

## Holidays and weekly rest

Do not assume Friday for every company or establishment.

Use Holiday List / shift policy plus approved legal profile.

Holiday/rest-day work flows through approved Attendance/OT rules.

## Timezone

Company/site timezone is explicit.

Store unambiguous instants where integration evidence is involved and preserve the
source timezone/offset. Bangladesh-only sites can display Asia/Dhaka, but code
should not assume every future site is UTC+6.

## Currency

Do not hardcode BDT inside reusable payroll services. Company/default salary
currency should drive native documents. Bangladesh-specific compliance may assume
BDT only where the legal profile explicitly requires it.

## Multi-company transfer

A cross-company transfer is not merely a department update.

Flow requires review of:

- end/effective employment relation in old company;
- new company placement;
- new salary assignment;
- leave handling;
- payroll cutoff/final settlement as policy requires;
- cost center/accounting;
- tax/statutory continuity;
- User Permission scope;
- biometric/device access;
- payment data.

No salary structure assignment from the wrong company may survive.

## Configuration health

Create a readiness report per company:

~~~text
Company profile               READY
Legal regime                  READY
Holiday/calendar              READY
Attendance model              READY
Salary structures             READY
Pay-basis coverage            224/226
Tax profile                   BLOCKED
PF/pension                    NOT USED / NEEDS DECISION
Gratuity                      NEEDS REVIEW
Accounting profile            READY
Payment methods               READY
~~~

Distinguish "not applicable", "not used", "not configured", "draft", and
"approved". Do not collapse them into null.

## Portability rule

Tradexcel-specific names may appear in seed/demo/configuration data, but reusable
domain services should receive Company/policy identifiers as arguments. Avoid
functions whose core behavior assumes TCL, EFL, one branch, one site or one wage.
