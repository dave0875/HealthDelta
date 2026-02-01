# ADR 6: Governance Anchors and Rewrite-Tolerant Enforcement

- Status: Accepted
- Date: 2026-02-01
- Issue: #130

## Context

Governance checks previously depended on commit-range assumptions (`before..after`, stable ancestry, fully available history). In real delivery flows, rebases, force-pushes, squash merges, and shallow fetches are normal. Treating commit SHAs as audit anchors caused brittle failures and confusing CI outcomes.

## Decision

1. Commit SHAs are implementation details, not governance anchors.
2. Authoritative governance anchors are:
   - PR title/body metadata
   - merge/release metadata
   - `.ai/` audit artifacts (prompt/session/time entries)
3. Commit-level footer checks remain best-effort and rewrite-tolerant:
   - attempt range resolution from merge parents/event payload
   - fall back to merge-base or HEAD-only checks
   - never crash when ranges are missing
4. CI executes tests/build validation even if governance checks fail; policy failures are surfaced explicitly after validation runs.

## Consequences

- Governance intent is preserved while reducing false negatives from git mechanics.
- Policy failures become actionable ("what happened", "what was checked instead", "how to fix").
- CI reliability improves under parallel work and rewritten history.

## Non-Goals

- No new governance requirements.
- No manual approvals or human-memory-only rules.
