# issue_2_followup_1

Issue: https://github.com/dave0875/HealthDelta/issues/2
Immutable base prompt: `.codex/prompts/issue_2.md`

This follow-up prompt:
- Explicitly references Issue #2 and `.codex/prompts/issue_2.md`
- Does NOT change Issue #2 scope or acceptance criteria
- Records post-hoc execution constraints and governance rules discovered during Issue #2 work

## Execution constraints (recorded)

- All repository mutations (code, workflows, docs, commits, pushes) are executed ONLY on the Ubuntu host “GORF”.
- macOS machines are NEVER used for repository mutation.
- The self-hosted macOS ARM64 runner (labels: self-hosted, macOS, arm64, xcode) is authoritative for Xcode/iOS work and is used ONLY via GitHub Actions.
- Xcode execution must always be validated via CI artifacts, never “trust me”.
- The runner has been proven operational via a successful workflow_dispatch execution.

