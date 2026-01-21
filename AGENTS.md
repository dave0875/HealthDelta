# HealthDelta — Operating Rules (HARD REQUIREMENTS)

This repository is run with strict, issue-driven Agile discipline and a Codex-auditable workflow.

## Non-negotiables

1) GitHub Issues are the system of record (hard stop)
- No code, refactors, formatting, renames, or behavior-changing docs without a GitHub issue that explains *why* first.
- If no issue exists: create one using the required template, then proceed.

2) Mandatory issue template
Every issue must use:

---
Story
As a <user/system>,
I want <capability>,
So that <clear outcome or value>.

Context / Why
Why this story matters now.
What risk, confusion, or limitation exists without it.

Acceptance Criteria
- Given <context>, when <action>, then <observable result>
- All criteria must be objective and testable.

Out of Scope
What this story explicitly does NOT attempt to solve.

Notes
Optional clarifications or constraints.
---

3) Trunk-based development
- `main` is always releasable.
- Short-lived branches; merge when acceptance criteria are met.
- No speculative/preparatory code.

4) TDD (required for non-trivial logic)
- Write failing tests first for non-trivial logic (especially identity resolution, parsing, anchors, dedupe).

5) Codex audit trail is mandatory
- Record substantial prompts in `.codex/prompts/`.
- Record each session in `.codex/sessions/YYYY-MM-DD/session_<n>.md`.
- Record architectural decisions as ADRs in `.codex/decisions/`.
- `.codex/` must never contain secrets.
- Additional architecture ADRs may be recorded under `docs/adr/` when explicitly required by an issue; these ADRs must be referenced from this file.

6) TIME.csv is mandatory
- Every work session appends a row referencing a GitHub issue.

7) GitHub interaction
- Use `gh` CLI for issues/PRs. No direct REST API calls.

## Runbooks
- Xcode + self-hosted runner operations are documented in `docs/runbook_xcode.md` and must be followed for iOS work and CI reliability.
- Ingest staging operations are documented in `docs/runbook_ingest.md` and must be followed for bootstrap ingest work.
- Identity bootstrap operations are documented in `docs/runbook_identity.md` and must be followed for canonical identity work.
- De-identification operations are documented in `docs/runbook_deid.md` and must be followed for share-safe dataset work.
- Pipeline orchestration is documented in `docs/runbook_pipeline.md` and must be followed for orchestrated runs.
- NDJSON export operations are documented in `docs/runbook_ndjson.md` and must be followed for canonical stream export work.
- NDJSON validation is documented in `docs/runbook_ndjson_validate.md` and must be followed to verify canonical stream outputs and guard against share-safety regressions.
- DuckDB loader/query operations are documented in `docs/runbook_duckdb.md` and must be followed for local analytics work.
- Reporting operations are documented in `docs/runbook_reports.md` and must be followed for share-safe summary artifacts.
- Incremental run registry operations are documented in `docs/runbook_incremental.md` and must be followed for stateful runs.
- Operator end-to-end command usage is documented in `docs/runbook_operator.md` and is the preferred entrypoint for operators.
- Doctor’s note summary output is documented in `docs/runbook_note.md` and must be followed for share-safe copy/paste summaries.
- Export directory profiling is documented in `docs/runbook_profile.md` and is the required first step before running ingest/pipeline on a new unpacked export directory.

## ADRs
- Doctor’s Note architecture (reusable component + operator integration): `docs/adr/ADR_3_doctors_note_architecture.md`

## Project Plan
- Living plan/backlog: `docs/plan.md` (share-safe; links to the prioritized next GitHub issues)

## Codex Governance (Binding Project Law)

### Codex Prompt Discipline
- Each GitHub Issue `N` has exactly one immutable prompt: `.codex/prompts/issue_N.md`.
- Once work begins on Issue `N`, `.codex/prompts/issue_N.md` is read-only and must never be edited, regenerated, or replaced.
- Post-hoc clarifications or execution constraints are recorded only as: `.codex/prompts/issue_N_followup_X.md`, where `X` is in `[1–9]`.
- Follow-up prompts are append-only and must state explicitly that they do NOT change issue scope or acceptance criteria.
- Follow-up `9` is a forcing function: open a new GitHub issue instead of creating `issue_N_followup_10.md`.
- Numeric forks such as `issue_N.1`, `issue_N_part2`, `issue_N_part_2`, etc. are prohibited.

### Execution Discipline
- No code, workflow, or documentation changes without a GitHub Issue capturing *why*.
- All CI work must produce observable, persisted artifacts (logs + uploaded artifacts/test results).
- Self-hosted runners are authoritative; cloud runners must not substitute silently.
- Ambiguity pauses execution until clarified before proceeding.
