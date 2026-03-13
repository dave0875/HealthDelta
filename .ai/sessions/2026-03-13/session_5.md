Issue: #245

Summary
- Investigated the residual `/patients/current` failure after the `v0.0.8` ORIN backend deploy.
- Confirmed the live error detail was a permission denial reading `analysis/reports/coverage_by_person.csv` from the Apple bootstrap dataset.
- Implemented a narrow fix so share-safe report artifacts are written with readable file modes and `/patients/current` self-heals by regenerating reports if it encounters an unreadable `coverage_by_person.csv`.

Verification Plan
- Run focused local tests for report artifact modes and `/patients/current` recovery.
- Push to `main`, wait for CI and Release.
- Validate `/patients/current` returns 200 against live ORIN current dataset.
