# Issue 87 Prompt

Date: 2026-01-30

User request
- "I want that. Do it please, and once this is done, tested, and deployed let's continue" (enforce UTC timezone for tests).

Scope for Issue #87
- Ensure CI runs tests with TZ=UTC.
- Document UTC test policy for local runs.
- Run tests to confirm.

Constraints
- Follow AGENTS.md governance (issue-driven changes, TDD for non-trivial logic).
- Keep outputs deterministic and share-safe.
