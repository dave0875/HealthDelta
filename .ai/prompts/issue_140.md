---
Story
As an operator,
I want ORIN deploy verification to run reliably regardless execute-bit state,
So that deploy proof does not fail with shell permission errors.

Context / Why
Manual ORIN deploy proof run failed with exit 126 because `scripts/cd/orin_verify_backend.sh` was invoked directly and not executable on the runner checkout. This is a tooling-path failure, not a deployment logic failure.

Acceptance Criteria
- ORIN deploy workflow no longer fails with `Permission denied` when running verify script.
- Deploy script invokes verify via `bash` to avoid dependence on file execute bit.
- A rerun of Deploy Backend (ORIN) with tag `v0.0.3` completes `Deploy + verify (compose)` successfully.

Out of Scope
- Changing backend application behavior.
- New governance requirements.

Notes
- Keep scope to command invocation hardening only.
---
