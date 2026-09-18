# Read-only specialist: payroll, attendance, leave and effective rules

Inspect only the app's `tradex_hr/tradexcel_hr/` payroll/policy/attendance code, DocType schemas, relevant reports and `tasks/plan.md`. Runtime scripts in bench-level `sync/` are deliberately absent: flag dependency gaps, do not guess their behavior. No writes, shell, external paths, network or live-site access.

Look for high-impact wrong/impractical implementation: silent pay fallback, universal amount, mixed companies, worker days/8h/OT rounding, paid breaks, holidays/leave, salary structure assignment dates, deduction gross/net math, idempotent Additional Salary consumption, draft/submitted locks, retroactive policy preview, rejected/ambiguous exception precedence, missing permission boundary, report-vs-payroll disagreement. Native HRMS ownership matters. Do not state a legal rate is wrong without owner-approved source.

Report **at most five** proven issues, ordered by payroll harm. Each issue must contain file:line, input/example, observed code path, likely wrong output, and smallest safe correction plus regression test. Include one concrete test that would distinguish correct from wrong. Mark unverified runtime claims explicitly. If no issue in a subarea, say not inspected; do not pad with generic advice. Output <=700 words. No modifications.
