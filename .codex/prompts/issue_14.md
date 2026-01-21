# Issue #14 — Operator integration for Doctor’s Note + ADR (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/14

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

A) Operator integration
- Modify `healthdelta run all` (Issue #12 operator command) so that after DuckDB + reports it invokes the Doctor’s Note builder (Issue #13) via direct function call (no subprocess).
- Output paths are deterministic:
  - `<base_out>/<run_id>/note/doctor_note.txt`
  - `<base_out>/<run_id>/note/doctor_note.md`
- Defaults:
  - In `--mode share`: generate Doctor’s Note.
  - In `--mode local`: generate Doctor’s Note by default.
- Optional flag: `--skip-note` disables note generation.

B) Incremental / no-op behavior
- If unchanged input triggers no-op:
  - do NOT regenerate Doctor’s Note
  - do NOT mutate any existing files
  - print deterministic console output pointing to existing note files

C) Run registry update
- Extend run registry entry `artifacts` to include relative pointers:
  - `note_dir`
  - `doctor_note_txt`
  - `doctor_note_md`

D) Tests (synthetic-only)
- Extend end-to-end operator test to assert:
  - note files exist at deterministic paths
  - note bytes are stable across reruns
  - banned tokens absent
  - no-op does not regenerate/modify note files
  - registry contains note pointers

E) Docs + ADR + governance
- Create ADR at `docs/adr/ADR_3_doctors_note_architecture.md` with required content and cross-references Issues #12/#13/#14.
- Reference this ADR from `AGENTS.md`.
- Update `docs/runbook_operator.md` to state operator auto-generates Doctor’s Note and references `docs/runbook_note.md`.

F) Evidence + closure
- Comment on Issue #12 clarifying: Doctor’s Note implemented in Issue #13 and integrated into operator in Issue #14.
- Comment on Issue #14 with CI run URL and artifact confirmation.
- Close Issue #14 only after CI is green (Linux + macOS, `ios-xcresult` present).

## Plan

1) Operator integration
- Update `healthdelta/operator.py`:
  - add `--skip-note` plumbing via `healthdelta/cli.py`
  - call `healthdelta.note.build_doctor_note(...)` after report generation
  - set note output dir to `<base_out>/<run_id>/note`
  - update console summary and registry pointers

2) Registry pointers
- Extend operator’s initial `artifacts` to include `note_dir`, `doctor_note_txt`, `doctor_note_md`.
- Update registry via `update_run_artifacts` after note generation.

3) No-op semantics
- Ensure the no-op path does not write files and prints note pointers from registry/defaults.

4) Tests + docs + ADR
- Update `tests/test_operator.py` to assert note file existence/byte stability/no-op no-mutation and registry pointers.
- Add ADR at `docs/adr/ADR_3_doctors_note_architecture.md` and reference from `AGENTS.md`.
- Update `docs/runbook_operator.md`.

5) Closeout
- Update `.codex/sessions/` + `docs/reviews/` + `TIME.csv`.
- Push, verify CI green, comment/close Issue #14, comment Issue #12.

