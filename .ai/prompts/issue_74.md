# Issue 74 Prompt

Date: 2026-01-30

User request
- "1" (proceed with Issue #74 after Issue #73).

Scope for Issue #74
- Add FHIR Procedure export to NDJSON with event_time from performed[x].
- Load Procedure rows into DuckDB and surface in reports.
- Extend tests to cover Procedure export, loader, and reporting.

Constraints
- Follow AGENTS.md governance (issue-driven changes, TDD for non-trivial logic).
- Keep outputs deterministic and share-safe.
