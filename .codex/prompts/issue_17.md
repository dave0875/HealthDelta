# Issue #17 — Export layout resolver (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/17

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

- Add a shared, testable resolver that returns paths (relative to export root) for:
  - `export.xml` (required)
  - `export_cda.xml` (optional)
  - clinical JSON directory (optional; prefer `clinical-records/`)
- Resolver must be deterministic and share-safe (no absolute paths in outputs/logs).
- Update `healthdelta export profile` to use the resolver.
- Add unit tests with synthetic directory variants.

## Design decisions (within scope)

- “Export root” is defined as the directory that contains `export.xml`.
  - If `--input` points to a directory that contains `export.xml`, that directory is the export root.
  - Otherwise, if `<input>/apple_health_export/export.xml` exists, then `<input>/apple_health_export` is the export root.
- Resolver returns only:
  - `export_root_rel` (relative to the provided `--input` directory)
  - `export_xml_rel`, `export_cda_rel`, `clinical_dir_rel` (relative to export root)
- Clinical JSON directory candidates (in order):
  - `clinical-records/`
  - `clinical/clinical-records/`

## Plan

1) Add `healthdelta/export_layout.py`
   - `ExportLayout` dataclass
   - `resolve_export_layout(input_dir: Path) -> ExportLayout`
2) Update `healthdelta/profile.py` to:
   - resolve export root and profile only that subtree
   - keep outputs share-safe (no absolute path leakage)
3) Add tests:
   - direct-root layout fixture (`export.xml` at input root)
   - wrapped layout fixture (`apple_health_export/export.xml`), plus an unrelated outer file to ensure it is excluded
   - unit tests for the resolver and/or profile behavior across both variants
4) Closeout:
   - `.codex/sessions/YYYY-MM-DD/session_17.md`
   - `docs/reviews/YYYY-MM-DD_17.md`
   - update `TIME.csv`
   - push, verify CI green, comment/close Issue #17.

