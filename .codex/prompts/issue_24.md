# Issue #24 — Operator: persistent identity across runs (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/24

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

- `healthdelta run all` uses a shared identity store rooted under `--state` (default: `<base_out>/state/identity`) so identity persists across runs.
- NDJSON export for operator runs continues to resolve `canonical_person_id` deterministically when identity is stored under state.
- Synthetic integration test proves stable `canonical_person_id` across two runs with same patient and no PII leakage.
- Update `docs/runbook_operator.md` to document identity persistence.
- Audit artifacts: session log, review artifact, `TIME.csv` row.
- CI green required before closing.

## Implementation sketch (likely changes)

- Operator (`healthdelta/operator.py`):
  - Change identity output directory from per-run `<run_id>/identity` to shared `<state>/identity`.
  - Ensure per-run directories remain deterministic and share-safe; share bundle already excludes `identity/`.
  - Update run registry artifacts as needed (optional) while keeping share-safe pointers.
- NDJSON exporter (`healthdelta/ndjson_export.py`):
  - Update identity discovery for operator runs so it can find `<base_out>/state/identity` (without relying on per-run identity).
  - Keep current fallback behavior (mapping.json single-person default) intact.
- Tests (`tests/test_operator.py`):
  - Add a new integration test that runs `healthdelta run all` twice on two different export dirs with the same synthetic patient name under the same `--out/--state` base and asserts the person id in NDJSON is stable.
- Docs:
  - Update `docs/runbook_operator.md` to describe shared identity location and its privacy implications (local-only; excluded from share bundles).

## Plan

1) Write failing test for stable `canonical_person_id` across two runs.
2) Implement shared identity store for operator run.
3) Update NDJSON identity resolution to discover state identity.
4) Run tests locally; push; verify CI; comment + close Issue #24.

