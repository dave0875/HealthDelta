# Session 3

- Date: 2026-03-12
- Issue: #233
- Goal: Make the Clinical Compass patient and window controls readable and lower-friction.

Actions
- Opened a follow-up issue after feedback that the patient and window controls were hard to read and confusing.
- Inspected the current scope card and confirmed that the patient affordance looked selectable without exposing real options, while the always-visible text field added unnecessary friction.
- Reworked the scope card so `Evaluation window` is a full-width readable selector rather than a compressed pill.
- Replaced the ambiguous patient pill with explicit patient options: `All patients`, the local iPhone record when known, and a secondary manual override path.
- Moved the raw manual patient text field behind an explicit affordance so it no longer dominates the scope card.
- Updated the iOS export runbook so the patient/window operator flow matches the redesigned scope controls.

Verification
- Ran focused iOS simulator coverage for `DashboardViewModelTests`; 16 tests passed, 0 failed.
- Ran the full iOS simulator suite on the MacBook Air after the scope-control redesign; 51 tests passed, 0 failed.
