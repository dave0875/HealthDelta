# Issue #13 — Doctor’s Note output (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/13

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

- Add CLI:
  - `healthdelta note build --db <path> --out <dir> [--mode local|share]`
- Write deterministic outputs under `--out`:
  - `doctor_note.txt`
  - `doctor_note.md`
- Constraints:
  - ≤ ~25 lines
  - deterministic ordering/formatting (byte-stable)
  - no PII: no names, no DOB, no free-text clinical notes, no identifiers embedded in fields
  - prefer aggregate-only (avoid `canonical_person_id` unless necessary)
- Minimum content:
  - Header: “HealthDelta Summary”, `run_id` (if present in DB), `generated_at` (ISO-8601)
  - Coverage: #people (distinct `canonical_person_id`), min/max `event_time`
  - Totals per table (observations/documents/(optional meds/conditions))
  - Counts by source (healthkit/fhir/cda)
  - Signals: top N observation types/codes if available (no free-text); otherwise omit and document
  - Footer disclaimer: “No names, dates of birth, or identifying text included.”
- Tests (synthetic-only) must:
  - build DB via Issue #9 loader pathway (from tiny synthetic NDJSON)
  - assert exact expected lines and byte stability across reruns
  - assert banned tokens absent (synthetic names/DOB)
- Docs:
  - add `docs/runbook_note.md`
  - reference from `AGENTS.md`
- Audit:
  - session log + review artifact + TIME.csv updates
- Close only when CI is green (Linux tests + macOS Xcode job with `.xcresult` artifact).

## Determinism + privacy decisions (within scope)

- `generated_at` must be ISO-8601 and byte-stable for the same DB:
  - Use a deterministic timestamp derived from DB content:
    - `generated_at = max(event_time)` across all tables (UTC, `Z`), else `1970-01-01T00:00:00Z`.
  - Document this in `docs/runbook_note.md`.
- Ensure stable ordering:
  - fixed section order
  - stable sort keys for “counts by source” and “signals”
  - newline-terminated outputs
- Do not include any free-text fields (documents, notes, narrative, etc.).

## Implementation plan

1) Implement `healthdelta/note.py`
   - `build_doctor_note(db_path: str, out_dir: str, mode: str) -> None`
   - Use DuckDB SQL aggregates (no full-table loads).
2) Wire CLI in `healthdelta/cli.py`
   - new top-level group: `note`
   - subcommand: `build`
3) Add tests `tests/test_note.py` (synthetic-only)
   - generate tiny NDJSON streams
   - build DuckDB via `healthdelta duckdb build`
   - run `healthdelta note build`
   - assert byte-stable outputs and banned tokens absent
4) Add `docs/runbook_note.md` and reference from `AGENTS.md`.
5) Audit closeout
   - `.codex/sessions/YYYY-MM-DD/session_<next>.md`
   - `docs/reviews/YYYY-MM-DD_13.md`
   - update `TIME.csv`
   - push, verify CI green, comment evidence, close Issue #13.

