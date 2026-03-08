# Session 9 - 2026-03-08

Issue: #175

Goal
- Add a single operator flow that validates NDJSON outputs and produces a verified share-safe bundle.

Notes
- Implemented `healthdelta run all --bundle-out <path>.tar.gz` in share mode.
- Added operator flow steps to:
  - export NDJSON
  - run `healthdelta export validate` logic and persist `validation/ndjson_validate.log`
  - build a share bundle from the run root
  - verify the produced bundle before returning success
- Updated runbooks for the operator and share bundle flows.
- Added operator coverage asserting that a bundle produced from `run all` includes the validation artifact and passes `share verify`.

Local verification
- `python3 -m healthdelta run all --help`
- `TZ=UTC python3 -m unittest tests/test_share_bundle.py -v`
- `TZ=UTC python3 -m unittest tests/test_operator.py -v` (skipped locally because `duckdb` is not installed in this environment)
