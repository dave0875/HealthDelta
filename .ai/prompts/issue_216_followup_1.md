Issue: #216 follow-up 1

This follow-up does NOT change issue scope or acceptance criteria.

Purpose
- Continue Issue #216 after the first physical-device export retest exposed an iOS privacy-config crash instead of a successful Health authorization prompt.

Execution constraints
- Reuse Issue #216 scope and acceptance criteria exactly as written in `.ai/prompts/issue_216.md`.
- Keep the fix minimal and focused on the first manual export path.
- Capture concrete device proof that tapping `Export Now` no longer crashes on missing Health usage-description metadata.
