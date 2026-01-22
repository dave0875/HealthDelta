Issue: https://github.com/dave0875/HealthDelta/issues/27

Scope / intent (immutable)
- Add `healthdelta share verify` to validate a share bundle’s allowlisted contents and integrity.
- Ensure verification is deterministic, share-safe (no absolute paths), and has clear exit codes.
- If needed, extend share bundle format to include a manifest of `path,size,sha256` for all archived files.

Acceptance criteria (restated)
- New CLI: `healthdelta share verify --bundle <path>.tar.gz`.
- Verification checks:
  - only allowlisted paths under `<run_id>/` are present (no `staging/`, no `identity/`)
  - `<run_id>/registry/run_entry.json` exists and parses as JSON
  - manifest exists and every file’s `path,size,sha256` matches extracted bytes (and no extra files exist outside the manifest)
- Deterministic output ordering and non-zero exit codes on failure.
- Synthetic tests cover passing and failing bundles.
- Update `docs/runbook_share_bundle.md` with verify usage.
- Audit artifacts + CI green required before closing.

Plan
1) Extend `healthdelta/share_bundle.py` to write a deterministic manifest (CSV) into the bundle under `<run_id>/registry/`.
2) Implement `healthdelta share verify`:
   - enumerate tar members deterministically
   - enforce allowlist rules
   - validate `run_entry.json`
   - validate manifest hashes/sizes vs extracted member bytes
3) Update/extend `tests/test_share_bundle.py`:
   - success case: bundle -> verify passes
   - failure cases: disallowed path and/or manifest hash mismatch
4) Update `docs/runbook_share_bundle.md` to document verification.

Determinism rules
- Bundle manifest ordering is lexicographic by archive path.
- Verifier emits messages sorted by path and uses stable wording.
- No timestamps, random IDs, or absolute local paths in outputs.

Privacy rules
- Verifier must not print absolute paths; only archive member paths.
- Verifier must not print file contents; only counts and checksums.

Execution constraints
- All repository mutations executed only on Ubuntu host `GORF`.
- GitHub interactions via `gh` CLI only.
