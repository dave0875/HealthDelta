# Session 17

- Date: 2026-03-11
- Issue: #230
- Goal: Make ORIN accumulate iPhone incremental uploads into a cumulative current dataset instead of replacing prior state.

Actions
- Confirmed the current iPhone direct-upload path sends one selected run at a time and that ORIN currently repoints `datasets/current` to that single uploaded zip.
- Verified the product gap with real data: the phone and Mac still hold the original full iPhone export while ORIN current was only analyzing a later five-row incremental delta.
- Scoped the implementation to the ORIN upload plane so raw uploaded runs remain preserved while a new cumulative current dataset is materialized and used for downstream insights.
- Added failing tests that prove a second iPhone upload must accumulate into current state, repeated uploads of the same run must not duplicate rows, and `/insights/current` must analyze the cumulative three-row view instead of the latest two-row delta.
- Implemented cumulative iPhone finalization in `healthdelta/upload_plane.py` so ORIN preserves raw uploaded run zips under `raw_uploads/`, writes a merged canonical `export.zip`, and keeps non-iPhone upload behavior unchanged.
- Updated the iOS/ORIN runbooks to document that iPhone uploads now accumulate on ORIN and that ORIN insights are grounded in the cumulative current dataset by default.

Verification
- `TZ=UTC python3 -m unittest tests.test_upload_plane -v`
- `TZ=UTC .venv/bin/python -m unittest tests.test_backend_upload_api tests.test_backend_insights_api -v`
