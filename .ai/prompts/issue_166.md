# Issue #166 Prompt (Immutable)

Implement a minimal authenticated upload + dataset control API in the existing backend server.

Scope:
- Add endpoints:
  - GET /datasets/current
  - POST /datasets/archive
  - GET /datasets/archives
  - POST /upload-sessions
  - PUT /upload-sessions/{id}/chunks/{index}
  - POST /upload-sessions/{id}/finalize
  - GET /upload-sessions/{id}
- Require bearer auth for new endpoints via `HEALTHDELTA_UPLOAD_TOKEN`.
  - If unset, return 503 with actionable error.
- Store data under `HEALTHDELTA_DATA_DIR` (default `/data`) with on-disk session metadata/chunks.
- Finalize must assemble chunks into export.zip, verify size and optional sha256, publish dataset, and manage current pointer.
- Add tests for bookkeeping/path handling and an integration-style endpoint flow.
- Update runbooks with token configuration and curl chunk-upload examples.
- Keep /healthz and /version behavior unchanged.
