# Issue #19 — Pipeline/operator: remove redundant CDA staging (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/19

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

- Pipeline and operator rely on ingest staging/layout for `export_cda.xml` and do not implement independent CDA staging.
- Share mode deid still receives `export_cda.xml` when present in the input export.
- Tests prove CDA presence through the pipeline/operator path.

## Plan

1) Remove redundant CDA staging helpers from:
   - `healthdelta/pipeline.py`
   - `healthdelta/operator.py`
2) Strengthen tests to prove the behavior end-to-end:
   - `tests/test_pipeline.py`: assert pipeline does not report/perform independent CDA staging; CDA still appears in deid output.
   - `tests/test_operator.py`: assert share-mode operator run produces deid CDA and at least one CDA-derived NDJSON observation.
3) Closeout:
   - session log `/.codex/sessions/YYYY-MM-DD/session_19.md`
   - review notes `docs/reviews/YYYY-MM-DD_19.md`
   - update `TIME.csv`
   - push; verify CI is green; comment + close Issue #19.

