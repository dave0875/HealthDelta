from __future__ import annotations

import datetime as dt
import hashlib
import json
import platform
import sys
import zipfile
from pathlib import Path
from typing import Any

from healthdelta.deid import deidentify_run
from healthdelta.identity import build_identity
from healthdelta.ingest import ingest_to_staging
from healthdelta.state import (
    artifact_pointers_for_run,
    compute_input_fingerprint,
    compute_run_id,
    read_last_run_id,
    register_run,
    run_input_fingerprint_sha256,
    write_last_run_id,
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _healthdelta_version() -> str:
    try:
        from importlib.metadata import version

        return version("healthdelta")
    except Exception:
        return "0.0.0+local"


def _redacted_input_summary(input_path: Path) -> dict:
    summary: dict[str, object] = {
        "path_redacted": True,
        "kind": "zip" if input_path.is_file() else "dir",
        "path_hint": "export.zip" if input_path.is_file() else "export_dir",
    }
    if input_path.is_file():
        summary["sha256"] = _sha256_file(input_path)
        summary["size_bytes"] = input_path.stat().st_size
    return summary


def _stage_export_cda_if_present(input_path: Path, run_dir: Path) -> dict | None:
    target_rel = Path("source") / "unpacked" / "export_cda.xml"
    target = run_dir / target_rel

    if input_path.is_dir():
        candidates = [
            input_path / "export_cda.xml",
            input_path / "apple_health_export" / "export_cda.xml",
        ]
        src = next((p for p in candidates if p.exists()), None)
        if src is None:
            return None
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(src.read_bytes())
        return {"staged": True, "path": target_rel.as_posix(), "sha256": _sha256_file(target), "size_bytes": target.stat().st_size}

    if input_path.is_file() and zipfile.is_zipfile(input_path):
        with zipfile.ZipFile(input_path) as zf:
            members = sorted([m for m in zf.namelist() if not m.endswith("/") and m.lower().endswith("export_cda.xml")])
            if not members:
                return None
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(members[0]) as src:
                target.write_bytes(src.read())
        return {"staged": True, "path": target_rel.as_posix(), "sha256": _sha256_file(target), "size_bytes": target.stat().st_size}

    return None


def run_pipeline(
    *,
    input_path: str,
    base_dir: str = "data",
    mode: str = "local",
    expected_run_id: str | None = None,
    skip_deid: bool = False,
    state_dir: str | None = None,
    since: str = "last",
    note: str | None = None,
) -> int:
    started_at = _now_utc()

    input_p = Path(input_path)
    base = Path(base_dir)
    staging_root = base / "staging"
    identity_dir = base / "identity"
    deid_root = base / "deid"

    if mode not in {"local", "share"}:
        print("ERROR: --mode must be one of: local, share", file=sys.stderr)
        return 2

    parent_run_id: str | None = None
    input_fingerprint: dict[str, object] | None = None
    if state_dir is not None:
        if since == "last":
            parent_run_id = read_last_run_id(state_dir)
        else:
            parent_run_id = since or None

        input_fingerprint = compute_input_fingerprint(input_p)
        fp_sha = input_fingerprint.get("sha256") if isinstance(input_fingerprint.get("sha256"), str) else None
        if fp_sha is None:
            print("ERROR: failed to compute input_fingerprint.sha256", file=sys.stderr)
            return 2

        if parent_run_id is not None:
            parent_fp = run_input_fingerprint_sha256(state_dir, parent_run_id)
            if parent_fp is not None and parent_fp == fp_sha:
                if expected_run_id is not None and expected_run_id != parent_run_id:
                    print(f"ERROR: --run-id {expected_run_id} does not match existing run_id {parent_run_id}", file=sys.stderr)
                    return 2
                if read_last_run_id(state_dir) is None:
                    write_last_run_id(state_dir, parent_run_id)
                print("no changes detected")
                print(f"run_id={parent_run_id}")
                return 0

        run_id = compute_run_id(parent_run_id=parent_run_id, input_fingerprint_sha256=fp_sha)
    else:
        run_id = None

    ingest_run_dir = ingest_to_staging(input_path=str(input_p), staging_root=str(staging_root), run_id_override=run_id)
    run_id_actual = ingest_run_dir.name
    if expected_run_id is not None and expected_run_id != run_id_actual:
        print(f"ERROR: --run-id {expected_run_id} does not match computed run_id {run_id_actual}", file=sys.stderr)
        return 2

    ingest_manifest_path = ingest_run_dir / "manifest.json"
    ingest_layout_path = ingest_run_dir / "layout.json"
    ingest_manifest_sha256 = _sha256_file(ingest_manifest_path) if ingest_manifest_path.exists() else None

    staged_cda = _stage_export_cda_if_present(input_p, ingest_run_dir)

    build_identity(staging_run_dir=str(ingest_run_dir), output_dir=str(identity_dir))

    deid_executed = False
    deid_out_dir = deid_root / run_id_actual
    if mode == "share" and not skip_deid:
        deidentify_run(staging_run_dir=str(ingest_run_dir), identity_dir=str(identity_dir), out_dir=str(deid_out_dir))
        deid_executed = True

    run_report_path = ingest_run_dir / "run_report.json"
    report: dict[str, object] = {
        "run_id": run_id_actual,
        "timestamps": {"started_at": started_at, "finished_at": _now_utc()},
        "mode": mode,
        "skip_deid": bool(skip_deid),
        "input": _redacted_input_summary(input_p),
        "state": {"enabled": bool(state_dir), "since": since, "parent_run_id": parent_run_id},
        "stages": {
            "ingest": {
                "executed": True,
                "run_dir": ingest_run_dir.as_posix(),
                "manifest_sha256": ingest_manifest_sha256,
                "layout_path": ingest_layout_path.as_posix(),
            },
            "identity": {
                "executed": True,
                "output_dir": identity_dir.as_posix(),
                "people_path": (identity_dir / "people.json").as_posix(),
                "aliases_path": (identity_dir / "aliases.json").as_posix(),
            },
            "deid": {
                "executed": deid_executed,
                "output_dir": deid_out_dir.as_posix() if deid_executed else None,
            },
        },
        "counts": {},
        "tool_versions": {
            "python": platform.python_version(),
            "healthdelta": _healthdelta_version(),
        },
        "determinism": {
            "stable_fields": [
                "run_id",
                "mode",
                "skip_deid",
                "input.kind",
                "input.sha256",
                "stages.ingest.manifest_sha256",
                "stages.*.output_dir",
            ],
            "time_fields": ["timestamps.*"],
            "notes": [
                "Report must not include PII (no names/DOB/MRNs).",
                "Idempotency relies on ingest run_id and identity alias_key dedupe.",
            ],
        },
    }

    if ingest_manifest_path.exists():
        m = _read_json(ingest_manifest_path)
        if isinstance(m, dict) and isinstance(m.get("counts"), dict):
            report["counts"] = {"ingest": m["counts"]}
        if isinstance(m, dict) and isinstance(m.get("files"), list):
            report["counts"]["staged_file_count"] = len(m["files"])

    if staged_cda is not None:
        report["counts"]["staged_export_cda"] = staged_cda

    _write_json(run_report_path, report)

    if state_dir is not None and input_fingerprint is not None:
        register_run(
            state_dir=state_dir,
            run_id=run_id_actual,
            input_fingerprint=input_fingerprint,
            parent_run_id=parent_run_id,
            note=note,
            artifacts=artifact_pointers_for_run(state_dir=state_dir, run_id=run_id_actual, mode=mode),
        )
        write_last_run_id(state_dir, run_id_actual)

    print(f"run_id={run_id_actual}")
    print(f"staging_dir={ingest_run_dir}")
    print(f"run_report={run_report_path}")
    if deid_executed:
        print(f"deid_dir={deid_out_dir}")
    return 0
