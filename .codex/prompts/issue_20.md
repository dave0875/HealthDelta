# Issue #20 — NDJSON validation: schema checks + share-safe assertions (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/20

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

- Add `healthdelta export validate --input <ndjson_dir>` that:
  - verifies newline-delimited JSON objects (one object per line; no partial lines)
  - checks required keys per stream
  - supports banned token/pattern checks (configurable for synthetic test fixtures)
- Add synthetic-only tests with both passing and failing NDJSON cases.
- Add a short runbook documenting validator behavior.

## Design (within scope)

- Validate all `*.ndjson` files under `--input` (deterministically sorted).
- Stream validation:
  - line-by-line parsing; no full-file JSON loads
  - fail with deterministic, stable error messages (sorted by file + line)
- Required keys:
  - baseline keys for every record: `canonical_person_id`, `source`, `source_file`, `event_time`, `run_id`
  - stream-specific required keys may be added later; for this slice focus on baseline + filename-based stream identification.
- Share-safe assertions:
  - optional `--banned-token` (repeatable) and `--banned-regex` (repeatable)
  - tests supply synthetic tokens (e.g., `John Doe`, `1980-01-02`) to prove the guardrails work.

## Plan

1) Implement `healthdelta/ndjson_validate.py` with a streaming validator and stable error reporting.
2) Wire CLI: `healthdelta export validate --input <ndjson_dir> [--banned-token T] [--banned-regex R]`.
3) Add tests:
   - passing: minimal NDJSON fixtures with required keys
   - failing: malformed JSON, missing keys, banned token present
4) Document: `docs/runbook_ndjson_validate.md` (usage + exit codes + what is checked).
5) Closeout: session log, review notes, TIME.csv; push; verify CI green; comment + close Issue #20.

