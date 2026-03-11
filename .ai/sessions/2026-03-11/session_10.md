# Session 10

- Date: 2026-03-11
- Issue: #226
- Goal: Roll the live ORIN backend on port 8080 forward to the current artifact-grounded insights implementation from `main`.

Actions
- Confirmed the phone was hitting a stale ad hoc ORIN container tagged `healthdelta-backend:issue223-test` on port 8080 rather than the managed `/opt/healthdelta` deployment.
- Verified the running container still contained the old `/insights/current` code path that raises `uploaded dataset is missing manifest.json or ndjson/observations.ndjson`.
- Scoped the remediation to an in-place operational rollout that preserves `/opt/healthdelta/data`, the current upload token, and the existing Ollama configuration.
