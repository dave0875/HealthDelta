# Issue 73 Prompt

Date: 2026-01-30

User request
- "Yes, I want you to actually do all of this." (execute mission backlog), continue after Issue #87.

Scope for Issue #73
- Add FHIR Encounter export to NDJSON with event_time from Encounter.period.
- Load Encounter rows into DuckDB and surface in reports.
- Add/adjust tests to cover Encounter export, loader, and reporting.

Constraints
- Follow AGENTS.md governance (issue-driven changes, TDD for non-trivial logic).
- Keep outputs deterministic and share-safe.
