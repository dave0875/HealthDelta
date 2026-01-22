# ISSUE-0040: Docs: runbook for iOS incremental exports and ingestion

GitHub: https://github.com/dave0875/HealthDelta/issues/40

## Objective
Provide a safe, repeatable runbook for iOS incremental export artifacts and how to ingest them into the Python toolchain.

## Context / Why
HealthDelta now has multiple ingestion paths (Apple export.zip and iOS incremental). Without explicit docs, operators can easily misuse paths, leak sensitive artifacts, or run the wrong commands.

## Acceptance Criteria
- Given an iOS incremental export output directory, when following the runbook, then an operator can ingest it locally into the Python toolchain without ambiguity.
- Runbook clearly lists artifacts (NDJSON, manifest, anchors) and privacy constraints.
- `AGENTS.md` references `docs/runbook_ios_export.md`.

## Non-Goals
- UI instructions inside the iOS app.

## Risks
- Risk: Operators accidentally share iOS exports or stage directories.
  - Mitigation: Emphasize share-safe vs non-share-safe and recommend `healthdelta share bundle` only for share-safe artifacts.

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py'`
- CI: green run link + macOS `ios-xcresult` artifact

## Rollback Plan
- Revert doc changes; no runtime behavior impacted.

