# Issue #15 — Export profiling command (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/15

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

- Add CLI:
  - `healthdelta export profile --input <export_dir> --out <dir> [--sample-json N] [--top-files K]`
  - Directory-only input for this issue (no profiling zip).
- Write share-safe outputs under `<out>/` (no PII / no raw payload fragments / no exact timestamps):
  - `profile.json`
  - `profile.md`
  - `files_top.csv` (top K by size; relative path only)
  - `counts_by_ext.csv`
  - `healthkit_record_types.csv` (if `export.xml` exists)
  - `clinical_resource_types.csv` (if clinical JSON exists; sample first N deterministically)
  - `cda_tag_counts.csv` (if `export_cda.xml` exists; tag names only; top N)
- Performance guardrails:
  - streaming/grep-like scanning for HealthKit Record type counts (no full DOM)
  - JSON resourceType: read only top-level `resourceType` and nothing else; deterministic sampling
  - CDA tag counts: streaming-safe tag scanner (no full DOM), top N only
- Synthetic-only fixtures and tests:
  - assert byte-stable outputs across reruns
  - assert banned tokens absent
  - assert correct counts + deterministic ordering
- Docs:
  - add `docs/runbook_profile.md` and reference from `AGENTS.md` as required first step before pipeline on new export dirs
- Close only after CI is green (Linux tests + macOS `ios-xcresult` artifact).

## Determinism + privacy decisions (within scope)

- Outputs must not include:
  - absolute paths, input directory names, file mtimes, or wall-clock “generated_at”
  - any extracted XML/JSON text/values beyond allowed schema-level strings
- Allowed emitted strings are strictly:
  - relative paths within the export root
  - file sizes
  - HK `Record` `type=` strings
  - FHIR top-level `resourceType` values
  - CDA tag local names (no attributes/text)
- CSV ordering:
  - stable sort keys documented in code
  - newline-terminated
- JSON serialization:
  - stable `sort_keys=True` and newline-terminated.

## Implementation plan

1) Add module `healthdelta/profile.py`
   - file listing and extension counts
   - HealthKit `export.xml` Record type counter (stream scan)
   - clinical JSON resourceType counter (deterministic sampling; read minimal bytes)
   - CDA tag counter (stream scan; local names; top N)
   - writer helpers for stable JSON/CSV/Markdown
2) Wire CLI: `healthdelta export profile` in `healthdelta/cli.py`.
3) Add fixtures under `tests/fixtures/profile_export/`:
   - `export.xml`, `export_cda.xml`, `clinical-records/*.json` (with embedded banned tokens in payloads to prove we don’t emit them)
4) Add tests `tests/test_profile.py`:
   - run command twice and assert exact bytes identical
   - assert expected counts for HK types, FHIR resourceTypes, CDA tags, ext counts, and top files
   - assert banned tokens absent across all outputs
5) Docs + governance updates:
   - add `docs/runbook_profile.md`
   - reference from `AGENTS.md`
6) Closeout:
   - `.codex/sessions/YYYY-MM-DD/session_15.md`
   - `docs/reviews/YYYY-MM-DD_15.md`
   - update `TIME.csv`
   - push, verify CI green, comment/close Issue #15 with run URL.

