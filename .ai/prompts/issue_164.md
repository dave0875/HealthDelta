# Issue #164 Prompt (Immutable)

Implement persistent ORIN backend data-plane mount and proof.

Scope:
- Add bind mount `/opt/healthdelta/data:/app/data` to ORIN backend compose deployment.
- Make deploy scripts idempotently create/check writable data dir without interactive sudo.
- Extend ORIN verification to prove:
  - image/version correctness
  - mount correctness (`/app/data` bind mount source)
  - sentinel write/read host+container correctness
  - sentinel persistence across restart
- Update ORIN deploy/CD runbooks so required host dirs and data-plane proof are explicit.
- Add lightweight tests validating compose and verify-script data-plane invariants.

Constraints:
- No database introduction, no new ingestion endpoints.
- Keep deploy mechanism aligned with existing ORIN compose path.
