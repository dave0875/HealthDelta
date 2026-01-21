# Issue #21 — Share bundle: package share-safe artifacts (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/21

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

- Add `healthdelta share bundle --run <base_out>/<run_id> --out <path>.tar.gz` that packages share-safe artifacts only:
  - `deid/` (if present)
  - `ndjson/`
  - `duckdb/`
  - `reports/`
  - `note/`
  - run registry entry snippet (share-safe, no PII)
- Deterministic archive ordering/metadata (as feasible).
- Synthetic tests prove `staging/` is excluded and the bundle output is byte-stable across repeated runs.

## Design (within scope)

- Treat `--run` as an operator-style run root: `<base_out>/<run_id>/`.
- Bundle layout inside the archive:
  - top-level directory is `<run_id>/...` to prevent collisions
  - include only whitelisted subtrees
  - include `registry/run_entry.json` containing a share-safe subset of `data/state/runs.json` for that run_id (or a minimal derived entry if state is missing)
- Determinism:
  - stable member ordering (sorted by archive path)
  - stable tar metadata: `mtime=0`, `uid=0`, `gid=0`, `uname=root`, `gname=root`
  - stable gzip header timestamp (`mtime=0`)

## Plan

1) Implement `healthdelta/share_bundle.py` using `tarfile` + `gzip` with deterministic metadata and ordering.
2) Wire CLI: `healthdelta share bundle --run ... --out ...`.
3) Add tests:
   - create a synthetic run_root containing both share-safe dirs and a `staging/` dir with banned tokens
   - assert tarball excludes `staging/` and is byte-identical across repeated runs
4) Document: `docs/runbook_share_bundle.md` and reference from `AGENTS.md`.
5) Closeout: session log, review notes, TIME.csv; push; verify CI green; comment + close Issue #21.

