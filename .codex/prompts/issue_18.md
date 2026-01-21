# Issue #18 — Ingest staging alignment + stage export_cda.xml (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/18

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

- Ingest uses the export layout resolver (Issue #17).
- For directory inputs, ingest stages:
  - `export.xml`
  - `export_cda.xml` (if present)
  - clinical records JSON files (and only that tree)
- `manifest.json` / `layout.json` include the CDA file when present and accurate counts.
- Tests cover both presence/absence of CDA and ensure no extra JSON is staged.

## Design decisions (within scope)

- Staging paths:
  - `export.xml` is staged at `source/export.xml` for directory inputs.
  - `export_cda.xml` is staged (when present) at `source/unpacked/export_cda.xml` and recorded as `layout.json.export_cda_xml`.
  - Clinical JSON files are staged under `source/clinical/clinical-records/` (canonicalized), regardless of whether the input directory uses `clinical-records/` or `clinical_records/`.
- For zip inputs, include `export_cda.xml` when present and restrict extracted clinical JSONs to clinical-records/clinical_records trees only.

## Plan

1) Extend `healthdelta/export_layout.py` clinical candidates to include underscore variants:
   - `clinical-records/`, `clinical_records/`, and nested under `clinical/`.
2) Update `healthdelta/ingest.py`:
   - directory inputs: resolve layout, copy export.xml, copy export_cda.xml if present, copy only clinical JSONs from resolved clinical dir into canonical staging path.
   - zip inputs: extract export_cda.xml if present and include it in layout; restrict JSON extraction to clinical trees.
   - update manifest file listing and layout keys accordingly.
3) Update tests:
   - adjust synthetic unpacked export builder to use `clinical-records/` (and add an extra JSON outside clinical dir to prove it is excluded).
   - add coverage for CDA present/absent for both dir and zip ingestion.
4) Closeout:
   - `.codex/sessions/YYYY-MM-DD/session_18.md`
   - `docs/reviews/YYYY-MM-DD_18.md`
   - update `TIME.csv`
   - push, verify CI green, comment/close Issue #18.

