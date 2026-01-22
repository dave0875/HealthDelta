# Issue 27 — Share bundle: add share verify (allowlist + hashes)

GitHub: https://github.com/dave0875/HealthDelta/issues/27

## Objective
Add a deterministic `healthdelta share verify` command to validate share bundles are allowlist-only and match recorded hashes, providing repeatable proof that staging/PII is excluded.

## Context
Issue #21 creates deterministic share bundles. A verifier reduces human error and provides an auditable check that bundles contain only share-safe artifacts.

## Acceptance Criteria (from GitHub issue)
- Add `healthdelta share verify --bundle <path>.tar.gz` that checks:
  - bundle contains only allowlisted paths under `<run_id>/` (no `staging/`, no `identity/`)
  - `registry/run_entry.json` exists and is valid JSON
  - all files match a bundle manifest of `path,size,sha256` (add manifest if needed)
- Deterministic output ordering and exit codes.
- Synthetic tests cover both passing and failing bundles.
- Update `docs/runbook_share_bundle.md` with verification usage.
- CI green required before closing.

## Non-goals
- Any network upload.
- Cryptographic signing of bundles (integrity is via embedded checksums only).

## Risks
- Tar path traversal or unexpected member types (must reject safely).
- Manifest self-referential hashing (avoid by excluding the manifest file itself from the manifest).

## Test Plan
- Create a deterministic bundle from synthetic run artifacts and assert `share verify` exits 0.
- Create failing synthetic bundles:
  - include a disallowed path (e.g., `<run_id>/staging/...`)
  - include an allowlisted file whose contents do not match the manifest sha256

## Rollback Plan
- Revert commits referencing Issue #27.
- Continue using `share bundle` without verifier.

