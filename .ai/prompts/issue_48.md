Issue: https://github.com/dave0875/HealthDelta/issues/48

Scope / intent (immutable)
- Add a minimal, share-safe backend HTTP service that can run in a container and supports CD verification:
  - `GET /healthz` returns HTTP 200 with a small JSON body
  - `GET /version` returns JSON including `version` and `git_sha`
- Provide a deterministic container entrypoint for the service.
- Provide local developer compose config and share-safe tests for the endpoints.

Acceptance criteria (restated)
- Running service responds to `/healthz` and `/version` as specified.
- Container build starts the service deterministically.
- Local compose brings up the service on a documented port.
- Tests cover health/version handlers and CI stays green.

Constraints
- Service must remain share-safe (no PHI/PII processing, no export handling).
- Prefer minimal dependencies.

