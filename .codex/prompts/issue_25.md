# Issue #25 — NDJSON schema: add `schema_version` + `record_key` (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/25

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

- Every emitted NDJSON row includes:
  - `schema_version` (integer)
  - `record_key` (string; deterministic hash; no PII)
- `healthdelta export validate` enforces presence/types for `schema_version` + `record_key`.
- Documentation updated (`docs/runbook_ndjson.md`).
- Synthetic tests prove:
  - `record_key` is stable across reruns
  - exporter remains byte-stable across reruns
- Audit artifacts: session log, review artifact, `TIME.csv` row.
- CI green required before closing.

## Design

- Introduce `schema_version=2` (since existing rows already include `event_key`; avoid retroactively redefining it).
- Define `record_key` as the existing per-row `event_key` value (sha256 of a stable payload), so it is deterministic and already used for dedupe.
- Keep `event_key` for backward compatibility with existing DuckDB/report tests; `record_key` becomes the canonical name moving forward.

## Plan

1) Update `healthdelta/ndjson_export.py` to add `schema_version` + `record_key` to every row.
2) Update `healthdelta/ndjson_validate.py` to enforce the new fields and their types.
3) Update synthetic tests:
   - `tests/test_ndjson_export.py` asserts `schema_version` and `record_key` exist and are stable
   - `tests/test_ndjson_validate.py` fixtures include the new fields
4) Update `docs/runbook_ndjson.md` to document the new fields.
5) Closeout: session log, review notes, TIME.csv; push; verify CI; comment + close Issue #25.

