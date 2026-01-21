from __future__ import annotations

import gzip
import io
import json
import tarfile
from pathlib import Path
from typing import Any

from healthdelta.state import load_registry


_ALLOWLIST_DIRS: tuple[str, ...] = ("deid", "ndjson", "duckdb", "reports", "note")


def _stable_json_bytes(obj: object) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _tarinfo_dir(name: str) -> tarfile.TarInfo:
    ti = tarfile.TarInfo(name=name.rstrip("/") + "/")
    ti.type = tarfile.DIRTYPE
    ti.mode = 0o755
    ti.uid = 0
    ti.gid = 0
    ti.uname = "root"
    ti.gname = "root"
    ti.mtime = 0
    ti.size = 0
    return ti


def _tarinfo_file(name: str, size: int) -> tarfile.TarInfo:
    ti = tarfile.TarInfo(name=name)
    ti.type = tarfile.REGTYPE
    ti.mode = 0o644
    ti.uid = 0
    ti.gid = 0
    ti.uname = "root"
    ti.gname = "root"
    ti.mtime = 0
    ti.size = size
    return ti


def _safe_run_registry_snippet(*, base_out: Path, run_id: str, present_dirs: list[str]) -> dict[str, Any]:
    state_dir = base_out / "state"
    entry: dict[str, Any] | None = None
    if state_dir.exists():
        runs = load_registry(str(state_dir))
        e = runs.get(run_id)
        if isinstance(e, dict):
            entry = e

    artifacts: dict[str, Any] = {}
    if isinstance(entry, dict) and isinstance(entry.get("artifacts"), dict):
        artifacts = {k: v for k, v in entry["artifacts"].items() if isinstance(k, str)}

    filtered_artifacts: dict[str, Any] = {}
    for k, v in artifacts.items():
        if not isinstance(v, str):
            continue
        if any(v.startswith(f"{run_id}/{d}") for d in present_dirs):
            filtered_artifacts[k] = v

    fp: dict[str, Any] | None = None
    if isinstance(entry, dict) and isinstance(entry.get("input_fingerprint"), dict):
        fp = entry["input_fingerprint"]

    fp_out: dict[str, Any] | None = None
    if isinstance(fp, dict):
        fp_out = {}
        for k in ["algorithm", "sha256", "file_count", "total_bytes"]:
            if k in fp:
                fp_out[k] = fp[k]

    return {
        "run_id": run_id,
        "created_at": entry.get("created_at") if isinstance(entry, dict) else None,
        "parent_run_id": entry.get("parent_run_id") if isinstance(entry, dict) else None,
        "input_fingerprint": fp_out,
        "artifacts": filtered_artifacts,
        "bundle_allowlist_dirs": present_dirs,
    }


def build_share_bundle(*, run_dir: str, out_path: str) -> None:
    run_root = Path(run_dir)
    if not run_root.is_dir():
        raise FileNotFoundError(f"--run must be a directory: {run_root}")

    run_id = run_root.name
    base_out = run_root.parent

    include_dirs = [d for d in _ALLOWLIST_DIRS if (run_root / d).is_dir()]
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Collect archive members deterministically.
    dir_names: set[str] = {f"{run_id}/"}
    file_members: list[tuple[str, Path]] = []

    for d in include_dirs:
        root_arc = f"{run_id}/{d}"
        dir_names.add(f"{root_arc}/")
        root_path = run_root / d
        for p in sorted([x for x in root_path.rglob("*")], key=lambda x: x.relative_to(run_root).as_posix()):
            if p.is_symlink():
                continue
            rel = p.relative_to(run_root).as_posix()
            arc = f"{run_id}/{rel}"
            if p.is_dir():
                dir_names.add(f"{arc}/")
            elif p.is_file():
                file_members.append((arc, p))

    snippet = _safe_run_registry_snippet(base_out=base_out, run_id=run_id, present_dirs=include_dirs)
    snippet_arc = f"{run_id}/registry/run_entry.json"
    dir_names.add(f"{run_id}/registry/")

    # Write deterministic tar.gz (stable gzip header mtime + stable tar metadata).
    with out.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", compresslevel=9, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tf:
                for dname in sorted(dir_names):
                    tf.addfile(_tarinfo_dir(dname))

                snippet_bytes = _stable_json_bytes(snippet)
                tf.addfile(_tarinfo_file(snippet_arc, size=len(snippet_bytes)), io.BytesIO(snippet_bytes))

                for arc, p in sorted(file_members, key=lambda t: t[0]):
                    size = p.stat().st_size
                    with p.open("rb") as f:
                        tf.addfile(_tarinfo_file(arc, size=size), f)
