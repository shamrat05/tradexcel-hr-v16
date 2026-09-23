# Statutory applicability review integrity

The employee-specific legal applicability decision is made by an authorized
Tradexcel Owner/Director with explicit company scope. The creator of the
Employee Separation cannot approve or mark their own separation as outside
worker scope, even if they also hold the Owner/Director role. Administrator
remains an administrative bypass.

`Not Applicable` has one narrow meaning: an independent reviewer has determined
that the employee is outside the selected worker scope. An employee governed by
another service-rule category must instead be reviewed against an exact,
approved, effective Rule Set with a matching separation-type and classification
mapping. No legal amount is calculated by this review.

The regression proof uses synthetic companies, employees, users, rule sets,
and a submitted Employee Separation on the v16 staging test site. It exercises
Frappe's actual Rule Set workflow transition and the statutory review endpoint.
The synthetic records are cleaned by the test. No real employee or legal rule
was changed.
