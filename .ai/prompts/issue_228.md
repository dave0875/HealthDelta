Issue: #228

Title: Fix iPhone upload archive relative paths

GitHub Issue URL: https://github.com/dave0875/HealthDelta/issues/228

Prompt
- Fix the iOS upload archive builder so uploaded run archives preserve the expected run-relative paths like `run_id/manifest.json` and `run_id/ndjson/observations.ndjson`.
- Eliminate malformed `private...` path fragments caused by brittle path-string replacement.
- Add an iOS regression test that specifically covers the `/private/...` versus `/var/...` path mismatch seen in real device uploads.
- Rebuild and redeploy the app, then confirm ORIN can read the uploaded run artifacts.
