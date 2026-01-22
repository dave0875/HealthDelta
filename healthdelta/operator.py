from __future__ import annotations

from pathlib import Path

from healthdelta.deid import deidentify_run
from healthdelta.duckdb_tools import build_duckdb
from healthdelta.identity import build_identity
from healthdelta.ingest import ingest_to_staging
from healthdelta.ndjson_export import export_ndjson
from healthdelta.reporting import build_report
from healthdelta.note import build_doctor_note
from healthdelta.state import (
    compute_input_fingerprint,
    compute_run_id,
    load_registry,
    read_last_run_id,
    register_run,
    run_input_fingerprint_sha256,
    update_run_artifacts,
    write_last_run_id,
)


def _artifact_paths(*, base_out: Path, run_id: str, include_deid: bool) -> dict[str, str | None]:
    run_root = base_out / run_id
    return {
        "staging_dir": f"{run_id}/staging",
        "identity_dir": "state/identity",
        "deid_dir": f"{run_id}/deid" if include_deid else None,
        "ndjson_dir": f"{run_id}/ndjson",
        "duckdb_db": f"{run_id}/duckdb/run.duckdb",
        "reports_dir": f"{run_id}/reports",
        "note_dir": f"{run_id}/note",
        "doctor_note_txt": f"{run_id}/note/doctor_note.txt",
        "doctor_note_md": f"{run_id}/note/doctor_note.md",
        "_run_root_exists": str(run_root.exists()),
    }


def _print_summary(*, run_id: str, base_out: Path, state_dir: Path, artifacts: dict[str, object], status: str) -> None:
    print(f"status={status}")
    print(f"run_id={run_id}")
    print(f"base_out={base_out.as_posix()}")
    print(f"state_dir={state_dir.as_posix()}")
    # Stable output ordering.
    for k in [
        "staging_dir",
        "identity_dir",
        "deid_dir",
        "ndjson_dir",
        "duckdb_db",
        "reports_dir",
        "note_dir",
        "doctor_note_txt",
        "doctor_note_md",
    ]:
        v = artifacts.get(k)
        print(f"{k}={'' if v is None else v}")


def run_all(
    *,
    input_path: str,
    base_out: str = "data",
    state_dir: str | None = None,
    since: str = "last",
    mode: str = "share",
    note: str | None = None,
    skip_note: bool = False,
) -> int:
    if mode not in {"local", "share"}:
        raise ValueError("--mode must be one of: local, share")

    base = Path(base_out)
    state = Path(state_dir) if state_dir is not None else base / "state"

    input_p = Path(input_path)

    parent_run_id: str | None
    if since == "last":
        parent_run_id = read_last_run_id(str(state))
    else:
        parent_run_id = since or None

    input_fingerprint = compute_input_fingerprint(input_p)
    fp_sha = input_fingerprint.get("sha256") if isinstance(input_fingerprint.get("sha256"), str) else None
    if fp_sha is None:
        raise ValueError("input_fingerprint.sha256 missing")

    # No-op detection using Issue #11 behavior.
    if parent_run_id is not None:
        parent_fp = run_input_fingerprint_sha256(str(state), parent_run_id)
        if parent_fp is not None and parent_fp == fp_sha:
            runs = load_registry(str(state))
            entry = runs.get(parent_run_id) if isinstance(runs.get(parent_run_id), dict) else {}
            artifacts = entry.get("artifacts") if isinstance(entry.get("artifacts"), dict) else {}
            if not artifacts:
                artifacts = _artifact_paths(base_out=base, run_id=parent_run_id, include_deid=(mode == "share"))
            _print_summary(run_id=parent_run_id, base_out=base, state_dir=state, artifacts=artifacts, status="no_changes")
            return 0

    run_id = compute_run_id(parent_run_id=parent_run_id, input_fingerprint_sha256=fp_sha)

    run_root = base / run_id
    staging_dir = run_root / "staging"
    identity_dir = state / "identity"
    deid_dir = run_root / "deid"
    ndjson_dir = run_root / "ndjson"
    duckdb_dir = run_root / "duckdb"
    reports_dir = run_root / "reports"
    note_dir = run_root / "note"
    duckdb_path = duckdb_dir / "run.duckdb"

    run_root.mkdir(parents=True, exist_ok=True)
    identity_dir.mkdir(parents=True, exist_ok=True)
    deid_dir.mkdir(parents=True, exist_ok=True)
    ndjson_dir.mkdir(parents=True, exist_ok=True)
    duckdb_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    note_dir.mkdir(parents=True, exist_ok=True)

    # Stage into a temporary run_id subdir then rename to <run_root>/staging to match operator layout.
    staged_tmp = ingest_to_staging(input_path=str(input_p), staging_root=str(run_root), run_id_override=run_id)
    if staging_dir.exists():
        raise FileExistsError(f"staging dir already exists: {staging_dir}")
    staged_tmp.replace(staging_dir)

    build_identity(staging_run_dir=str(staging_dir), output_dir=str(identity_dir))

    include_deid = mode == "share"
    if include_deid:
        deidentify_run(staging_run_dir=str(staging_dir), identity_dir=str(identity_dir), out_dir=str(deid_dir))

    artifacts = {
        "staging_dir": f"{run_id}/staging",
        "identity_dir": "state/identity",
        "deid_dir": f"{run_id}/deid" if include_deid else None,
        "ndjson_dir": f"{run_id}/ndjson",
        "duckdb_db": f"{run_id}/duckdb/run.duckdb",
        "reports_dir": f"{run_id}/reports",
        "note_dir": f"{run_id}/note",
        "doctor_note_txt": f"{run_id}/note/doctor_note.txt",
        "doctor_note_md": f"{run_id}/note/doctor_note.md",
    }

    register_run(
        state_dir=str(state),
        run_id=run_id,
        input_fingerprint=input_fingerprint,
        parent_run_id=parent_run_id,
        note=note,
        artifacts=artifacts,
    )
    write_last_run_id(str(state), run_id)

    # NDJSON export
    if include_deid:
        export_ndjson(input_dir=str(deid_dir), out_dir=str(ndjson_dir), mode="share")
    else:
        export_ndjson(input_dir=str(staging_dir), out_dir=str(ndjson_dir), mode="local")

    update_run_artifacts(str(state), run_id, {"ndjson_dir": f"{run_id}/ndjson"})

    # DuckDB build
    build_duckdb(input_dir=str(ndjson_dir), db_path=str(duckdb_path), replace=True)
    update_run_artifacts(str(state), run_id, {"duckdb_db": f"{run_id}/duckdb/run.duckdb"})

    # Reports build
    build_report(db_path=str(duckdb_path), out_dir=str(reports_dir), mode=mode)
    update_run_artifacts(str(state), run_id, {"reports_dir": f"{run_id}/reports"})

    # Doctor's Note build (Issue #13)
    if not skip_note:
        build_doctor_note(db_path=str(duckdb_path), out_dir=str(note_dir), mode=mode)
        update_run_artifacts(
            str(state),
            run_id,
            {
                "note_dir": f"{run_id}/note",
                "doctor_note_txt": f"{run_id}/note/doctor_note.txt",
                "doctor_note_md": f"{run_id}/note/doctor_note.md",
            },
        )

    _print_summary(run_id=run_id, base_out=base, state_dir=state, artifacts=artifacts, status="created")
    return 0
