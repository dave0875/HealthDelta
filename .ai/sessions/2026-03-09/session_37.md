# Session 37 - 2026-03-09

Issue: #208

Goal
- Add a share-safe clinical evidence manifest to report outputs and bundled artifacts.

Notes
- Added deterministic `clinical_evidence_manifest.json` and `clinical_evidence_manifest.md` outputs to share-safe reports.
- Included resource counts, mapping coverage, unresolved-reference totals, and explicit redaction-status flags.
- Updated share-bundle tests and runbooks to reflect the new manifest artifacts.

Local verification
- `TZ=UTC .venv/bin/python -m unittest tests/test_reports.py tests/test_share_bundle.py -v`
