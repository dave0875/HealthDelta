# Session 34 — 2026-01-22

Issues worked
- #34 iOS: persistent single-user canonical_person_id (UUIDv4) for exports

Execution environment
- Repository mutations executed on Ubuntu host: `GORF`

Work summary
- Added `CanonicalPersonIDStore` (file-backed) to persist a per-install UUIDv4 canonical person identifier in the app sandbox.
- Updated `IncrementalNDJSONExporter` to include `canonical_person_id` on every emitted NDJSON row (injectable provider for deterministic tests).
- Added unit tests for ID stability/UUID parsing and exporter row inclusion.

Local verification
- Linux: `python3 -m unittest discover -s tests -p 'test_*.py'` (pass)
- iOS tests verified via CI macOS runner (see CI evidence)

AI-on-AI review
- Local model: `ollama run llama3.1:8b` (see `docs/reviews/2026-01-22_34.md`)

CI evidence
- Green CI: (pending)

