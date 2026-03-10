Issue: #216 follow-up 2

This follow-up does NOT change issue scope or acceptance criteria.

Purpose
- Continue Issue #216 after the post-privacy-fix device retest showed the app still cannot export because the signed app lacks the `com.apple.developer.healthkit` entitlement.

Execution constraints
- Reuse Issue #216 scope and acceptance criteria exactly as written in `.ai/prompts/issue_216.md`.
- Keep the fix minimal and focused on enabling the first manual HealthKit export path.
- Capture concrete device proof that tapping `Export Now` no longer fails on a missing HealthKit entitlement.
