# Issue #8 — Canonical NDJSON exporters (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/8

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

- Add `healthdelta export ndjson --input <pipeline_run_dir> --out <dir> [--mode local|share]` with no network access.
- Export deterministic, PII-free NDJSON streams from:
  - pipeline local outputs (staging + identity), and
  - pipeline share outputs (deid directory).
- Emit at minimum:
  - `observations.ndjson`
  - `documents.ndjson`
  - `medications.ndjson` (if present)
  - `conditions.ndjson` (if present)
- Every NDJSON line includes: `canonical_person_id`, `source`, `source_file`, `event_time`, `run_id`.
- Supported sources:
  - HealthKit `export.xml` (stream parse `<Record>` → observations)
  - FHIR JSON (single-resource files): `Observation`, `DocumentReference`, `MedicationRequest`, `Condition`
  - CDA `export_cda.xml` (streaming-safe parsing; document exported vs skipped)
- Determinism requirements:
  - same input + same identity + same mode ⇒ byte-stable NDJSON outputs
  - deterministic ordering with explicit sort keys
  - stable JSON serialization for each line
  - reruns do not duplicate records
- Tests must be synthetic-only and assert: files created, no PII, `canonical_person_id` on every line, stable outputs across reruns.
- Docs: add `docs/runbook_ndjson.md` and reference it from `AGENTS.md`.
- Audit artifacts required: session log, review artifact, TIME.csv entry. Close only when CI is green with artifacts.

## Plan (implementation modules + wiring)

1) Add new module `healthdelta/ndjson_export.py`
   - Resolve inputs for `--mode local|share`:
     - local: treat `--input` as staging run dir (`.../staging/<run_id>`); read `layout.json`; load identity from sibling `<base_dir>/identity`.
     - share: treat `--input` as deid run dir (`.../deid/<run_id>`) OR staging run dir; read deid `layout.json` + `mapping.json` when available.
   - Implement three extractors:
     - HealthKit XML: `xml.etree.ElementTree.iterparse` to stream `<Record>` elements.
     - FHIR JSON: load one file at a time; support the listed resourceTypes only.
     - CDA XML: streaming-safe `iterparse` extracting minimal “observation-like” entries (code/value/effectiveTime where available).
   - Build stable per-stream record lists, de-duplicate by stable `event_key`, sort by explicit sort key, and write NDJSON with stable JSON encoding.

2) CLI wiring in `healthdelta/cli.py`
   - Add `healthdelta export ndjson` command that calls exporter.

3) Tests + fixtures
   - Add synthetic-only fixtures inline in test(s) or under `tests/fixtures/`:
     - tiny HealthKit `export.xml` with 1–2 `<Record>` entries
     - tiny CDA with 1 observation-like entry + patient header containing synthetic name/DOB (must not appear in output)
     - tiny FHIR resources (Patient + Observation + DocumentReference + MedicationRequest + Condition)
   - Tests:
     - exporter creates expected NDJSON files and row counts
     - every row has required fields and no PII strings
     - running exporter twice yields identical bytes

4) Docs
   - Add `docs/runbook_ndjson.md` documenting:
     - per-stream schema fields
     - event_time selection rules
     - deterministic ordering/sort keys
     - source handling and CDA limitations (what’s skipped)
   - Update `AGENTS.md` to reference runbook.

5) Evidence + closeout
   - Run unit tests locally (Linux).
   - Push; verify CI green (Linux + self-hosted macOS jobs) with artifacts.
   - Perform AI-on-AI review with local Ollama; write `docs/reviews/YYYY-MM-DD_8.md`.
   - Write `.codex/sessions/YYYY-MM-DD/session_<n>.md` and update `TIME.csv`.
   - Comment Issue #8 with CI run link and usage notes; then close.

## Determinism rules (must be implemented)

- Stable per-record ID: `event_key = sha256(canonical minimal payload)`; used to dedupe within a run.
- Stable ordering: sort each stream by a documented tuple key (e.g., `event_time`, `canonical_person_id`, `source`, `source_file`, `source_id/event_key`).
- Stable JSON serialization:
  - `json.dumps(obj, sort_keys=True, separators=(",", ":"))`
  - newline-terminated output
- Output strategy: write each stream to a temp file then atomically replace to avoid partial outputs.

## Privacy rules (must be enforced)

- Do not emit names, DOBs, MRNs, patient identifiers, or raw subject references.
- Synthetic-only fixtures; never commit real health exports.
- `source_file` is always relative/redacted (no absolute host paths).

## Integration with pipeline outputs (#4–#7)

- Staging run dir comes from ingest/pipeline: `<base_dir>/staging/<run_id>/layout.json` + staged sources under `source/...`.
- Identity outputs are in `<base_dir>/identity/people.json` + `aliases.json`.
- Share outputs are in `<base_dir>/deid/<run_id>/` with `mapping.json`, `layout.json`, and de-identified copies under `source/...`.
