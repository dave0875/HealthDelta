# ISSUE-0018: Ingest staging alignment + stage export_cda.xml

GitHub: https://github.com/dave0875/HealthDelta/issues/18

## Objective
Make ingest staging consistent with canonical export layout, stage `export_cda.xml` when present, and restrict clinical JSON staging to the intended clinical records tree.

## Context / Why
Large exports make broad `rglob("*.json")` scans slow and risk staging unrelated JSON. CDA staging currently happens outside ingest, creating divergence. Consolidating in ingest improves determinism and performance while keeping outputs share-safe.

## Acceptance Criteria
- Ingest uses the export layout resolver.
- For directory inputs, ingest stages:
  - `export.xml`
  - `export_cda.xml` (if present)
  - clinical records JSON files (and only that tree)
- `manifest.json` / `layout.json` include the CDA file when present and accurate counts.
- Tests cover CDA present/absent and assert no extra JSON is staged.

## Non-Goals
- No changes to de-identification rules.
- No refactor of pipeline/operator CDA staging beyond what is required for ingest correctness (Issue #19).

## Risks
- Risk: real-world exports use different clinical records path variants.
  - Mitigation: support explicit known variants via the shared resolver (no broad scan).

## Test Plan
- Local: `python3 -m unittest discover -s tests`
- CI: verify green run (Linux + macOS) with `ios-xcresult` artifact.

## Rollback Plan
- Revert ingest changes; restore prior broad JSON scan behavior (undesirable but safe fallback).

