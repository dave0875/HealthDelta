Issue: #223

Follow-up prompt 1

This follow-up does not change issue scope or acceptance criteria.

Execution clarification
- The landing push for Issue #223 exposed an existing race in the macOS simulator tests for dashboard progress indicators.
- Stabilize those tests in the smallest way that removes the runner-dependent timing race without changing application behavior.
- Keep the fix under Issue #223 so the issue can satisfy its own CI proof.
