from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PIPELINE_VERSION_SALT = "healthdelta_pipeline_v1"
STATE_SCHEMA_VERSION = 1


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _stable_json_bytes(obj: object) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_if_changed(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_bytes()
        if existing == content:
            return
    path.write_bytes(content)


def _now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class StatePaths:
    state_dir: Path
    runs_json: Path
    last_run: Path


def resolve_state_paths(state_dir: str) -> StatePaths:
    sd = Path(state_dir)
    return StatePaths(
        state_dir=sd,
        runs_json=sd / "runs.json",
        last_run=sd / "LAST_RUN",
    )


def _base_dir_for_state(state_dir: Path) -> Path:
    # Default convention: <base>/state. If caller uses a different layout, we still anchor pointers to the parent.
    return state_dir.parent


def load_registry(state_dir: str) -> dict[str, dict]:
    paths = resolve_state_paths(state_dir)
    if not paths.runs_json.exists():
        return {}
    obj = _read_json(paths.runs_json)
    runs = obj.get("runs") if isinstance(obj, dict) else None
    if not isinstance(runs, dict):
        return {}
    out: dict[str, dict] = {}
    for k, v in runs.items():
        if isinstance(k, str) and isinstance(v, dict):
            out[k] = v
    return out


def save_registry(state_dir: str, runs: dict[str, dict]) -> None:
    paths = resolve_state_paths(state_dir)
    obj = {
        "schema_version": STATE_SCHEMA_VERSION,
        "runs": runs,
    }
    _write_if_changed(paths.runs_json, _stable_json_bytes(obj))


def read_last_run_id(state_dir: str) -> str | None:
    paths = resolve_state_paths(state_dir)
    if not paths.last_run.exists():
        return None
    text = paths.last_run.read_text(encoding="utf-8", errors="replace").strip()
    return text or None


def write_last_run_id(state_dir: str, run_id: str) -> None:
    paths = resolve_state_paths(state_dir)
    _write_if_changed(paths.last_run, (run_id + "\n").encode("utf-8"))


def compute_input_fingerprint(input_path: Path) -> dict[str, object]:
    """
    Deterministic, share-safe fingerprint:
    - hashes only relative paths + size_bytes + sha256(bytes)
    - does not store or print absolute input paths
    """
    if input_path.is_file():
        sha = _sha256_file(input_path)
        size = input_path.stat().st_size
        payload = f"file\0{size}\0{sha}\n".encode("utf-8")
        fp = hashlib.sha256(payload).hexdigest()
        return {"algorithm": "sha256(file size + file sha256)", "sha256": fp, "file_count": 1, "total_bytes": size}

    if not input_path.is_dir():
        raise ValueError(f"--input must be a file or directory: {input_path}")

    files: list[Path] = sorted([p for p in input_path.rglob("*") if p.is_file()], key=lambda p: p.relative_to(input_path).as_posix())
    h = hashlib.sha256()
    total = 0
    for p in files:
        rel = p.relative_to(input_path).as_posix()
        size = p.stat().st_size
        total += size
        sha = _sha256_file(p)
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(str(size).encode("ascii"))
        h.update(b"\0")
        h.update(sha.encode("ascii"))
        h.update(b"\n")
    return {
        "algorithm": "sha256(relpath + size + sha256(bytes)) over all files",
        "sha256": h.hexdigest(),
        "file_count": len(files),
        "total_bytes": total,
    }


def compute_run_id(*, parent_run_id: str | None, input_fingerprint_sha256: str) -> str:
    blob = f"{PIPELINE_VERSION_SALT}\n{parent_run_id or ''}\n{input_fingerprint_sha256}\n".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def register_run(
    *,
    state_dir: str,
    run_id: str,
    input_fingerprint: dict[str, object],
    parent_run_id: str | None,
    note: str | None,
    artifacts: dict[str, object],
    created_at: str | None = None,
) -> None:
    runs = load_registry(state_dir)
    if run_id in runs:
        return
    entry = {
        "run_id": run_id,
        "created_at": created_at or _now_utc(),
        "input_fingerprint": input_fingerprint,
        "parent_run_id": parent_run_id,
        "notes": note,
        "artifacts": artifacts,
    }
    runs[run_id] = entry
    save_registry(state_dir, runs)


def _sanitize_artifact_pointer(v: object) -> object:
    if isinstance(v, str):
        p = Path(v)
        if p.is_absolute():
            return p.name
    return v


def update_run_artifacts(state_dir: str, run_id: str, patch: dict[str, object]) -> None:
    runs = load_registry(state_dir)
    entry = runs.get(run_id)
    if not isinstance(entry, dict):
        raise KeyError(f"run_id not found in registry: {run_id}")

    artifacts = entry.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}

    changed = False
    for k, v in patch.items():
        if not isinstance(k, str) or not k:
            continue
        v = _sanitize_artifact_pointer(v)
        if artifacts.get(k) != v:
            artifacts[k] = v
            changed = True

    if not changed:
        return

    entry = {**entry, "artifacts": artifacts}
    runs[run_id] = entry
    save_registry(state_dir, runs)


def artifact_pointers_for_run(*, state_dir: str, run_id: str, mode: str) -> dict[str, object]:
    base = _base_dir_for_state(resolve_state_paths(state_dir).state_dir)
    # Store relative paths under the base dir (avoids absolute path leakage).
    def rel(p: Path) -> str:
        try:
            return p.relative_to(base).as_posix()
        except ValueError:
            return p.name

    staging_dir = base / "staging" / run_id
    deid_dir = base / "deid" / run_id
    return {
        "staging_dir": rel(staging_dir),
        "deid_dir": rel(deid_dir) if mode == "share" else None,
        "ndjson_dir": None,
        "duckdb_db": None,
        "reports_dir": None,
    }


def lookup_run(state_dir: str, run_id: str) -> dict[str, object] | None:
    return load_registry(state_dir).get(run_id)


def run_input_fingerprint_sha256(state_dir: str, run_id: str) -> str | None:
    entry = lookup_run(state_dir, run_id)
    if not isinstance(entry, dict):
        return None
    fp = entry.get("input_fingerprint")
    if isinstance(fp, dict) and isinstance(fp.get("sha256"), str):
        return fp["sha256"]
    return None


def register_existing_run_dir(*, run_dir: Path, state_dir: str, note: str | None = None) -> str:
    run_id = run_dir.name
    base = _base_dir_for_state(resolve_state_paths(state_dir).state_dir)
    parent_run_id = None

    # Fingerprint from staged manifest if present; otherwise fingerprint the run_dir content itself.
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = _read_json(manifest_path)
        except json.JSONDecodeError:
            manifest = None
        files = manifest.get("files") if isinstance(manifest, dict) else None
        h = hashlib.sha256()
        total_bytes = 0
        count = 0
        if isinstance(files, list):
            for item in sorted([x for x in files if isinstance(x, dict)], key=lambda x: str(x.get("path", ""))):
                path = item.get("path")
                size = item.get("size_bytes")
                sha = item.get("sha256")
                if not (isinstance(path, str) and isinstance(size, int) and isinstance(sha, str)):
                    continue
                total_bytes += size
                count += 1
                h.update(path.encode("utf-8"))
                h.update(b"\0")
                h.update(str(size).encode("ascii"))
                h.update(b"\0")
                h.update(sha.encode("ascii"))
                h.update(b"\n")
        input_fingerprint = {
            "algorithm": "sha256(staged manifest files[*].path + size_bytes + sha256)",
            "sha256": h.hexdigest(),
            "file_count": count,
            "total_bytes": total_bytes,
        }
    else:
        input_fingerprint = compute_input_fingerprint(run_dir)

    artifacts = {
        "staging_dir": None,
        "deid_dir": None,
        "ndjson_dir": None,
        "duckdb_db": None,
        "reports_dir": None,
    }
    try:
        artifacts["staging_dir"] = (run_dir.relative_to(base)).as_posix()
    except ValueError:
        artifacts["staging_dir"] = run_dir.name

    register_run(
        state_dir=state_dir,
        run_id=run_id,
        input_fingerprint=input_fingerprint,
        parent_run_id=parent_run_id,
        note=note,
        artifacts=artifacts,
    )
    write_last_run_id(state_dir, run_id)
    return run_id
