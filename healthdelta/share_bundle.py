from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from healthdelta.state import load_registry
from healthdelta.progress import progress


_ALLOWLIST_DIRS: tuple[str, ...] = ("deid", "ndjson", "duckdb", "reports", "note")
_REGISTRY_DIR = "registry"
_RUN_ENTRY_JSON = "run_entry.json"
_BUNDLE_MANIFEST_CSV = "bundle_manifest.csv"
_MANIFEST_HEADER = ["path", "size", "sha256"]


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


def _sha256_stream(f: io.BufferedReader) -> str:
    h = hashlib.sha256()
    for chunk in iter(lambda: f.read(1024 * 1024), b""):
        h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def _sha256_file(path: Path) -> str:
    with path.open("rb") as f:
        return _sha256_stream(f)


def _manifest_csv_bytes(entries: list[tuple[str, int, str]]) -> bytes:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(_MANIFEST_HEADER)
    for p, size, sha in entries:
        w.writerow([p, str(int(size)), sha])
    text = out.getvalue()
    if not text.endswith("\n"):
        text += "\n"
    return text.encode("utf-8")


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
        raise FileNotFoundError("--run must be an existing directory")

    run_id = run_root.name
    base_out = run_root.parent

    with progress.phase("bundle: collect members"):
        include_dirs = [d for d in _ALLOWLIST_DIRS if (run_root / d).is_dir()]
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        # Collect archive members deterministically.
        dir_names: set[str] = {f"{run_id}/"}
        file_members: list[tuple[str, Path]] = []
        task = progress.task("bundle: scan files", unit="paths")
        batch = 0

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
                batch += 1
                if batch >= 200:
                    task.advance(batch)
                    batch = 0
        if batch:
            task.advance(batch)

    with progress.phase("bundle: build manifest"):
        snippet = _safe_run_registry_snippet(base_out=base_out, run_id=run_id, present_dirs=include_dirs)
        snippet_arc = f"{run_id}/{_REGISTRY_DIR}/{_RUN_ENTRY_JSON}"
        dir_names.add(f"{run_id}/{_REGISTRY_DIR}/")

        # Manifest covers all regular files except the manifest itself.
        manifest_arc = f"{run_id}/{_REGISTRY_DIR}/{_BUNDLE_MANIFEST_CSV}"
        snippet_bytes = _stable_json_bytes(snippet)
        manifest_entries: list[tuple[str, int, str]] = [(snippet_arc, len(snippet_bytes), _sha256_bytes(snippet_bytes))]
        task = progress.task("bundle: hash files", total=len(file_members) + 1, unit="files")
        task.advance(1)
        for arc, p in sorted(file_members, key=lambda t: t[0]):
            manifest_entries.append((arc, p.stat().st_size, _sha256_file(p)))
            task.advance(1)
        manifest_entries = sorted(manifest_entries, key=lambda t: t[0])
        manifest_bytes = _manifest_csv_bytes(manifest_entries)

    # Write deterministic tar.gz (stable gzip header mtime + stable tar metadata).
    with progress.phase("bundle: write archive"):
        total_members = len(dir_names) + 2 + len(file_members)  # dirs + snippet + manifest + files
        task = progress.task("bundle: write archive", total=total_members, unit="members")

        with out.open("wb") as raw:
            with gzip.GzipFile(filename="", fileobj=raw, mode="wb", compresslevel=9, mtime=0) as gz:
                with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tf:
                    for dname in sorted(dir_names):
                        tf.addfile(_tarinfo_dir(dname))
                        task.advance(1)

                    tf.addfile(_tarinfo_file(snippet_arc, size=len(snippet_bytes)), io.BytesIO(snippet_bytes))
                    task.advance(1)

                    tf.addfile(_tarinfo_file(manifest_arc, size=len(manifest_bytes)), io.BytesIO(manifest_bytes))
                    task.advance(1)

                    for arc, p in sorted(file_members, key=lambda t: t[0]):
                        size = p.stat().st_size
                        with p.open("rb") as f:
                            tf.addfile(_tarinfo_file(arc, size=size), f)
                        task.advance(1)


def _is_safe_member_name(name: str) -> bool:
    if not name or name.startswith("/"):
        return False
    p = PurePosixPath(name)
    if p.is_absolute():
        return False
    if ".." in p.parts:
        return False
    return True


def verify_share_bundle(*, bundle_path: str) -> list[str]:
    bundle = Path(bundle_path)
    if not bundle.is_file():
        return [f"missing bundle file: {bundle.name}"]

    errors: list[str] = []

    with progress.phase("bundle: verify"):
        with tarfile.open(bundle, mode="r:gz") as tf:
            members = [m for m in tf.getmembers() if m.name]
            names = [m.name for m in members]

            task = progress.task("bundle: verify members", total=len(members), unit="members")
            batch = 0

            for n in sorted(names):
                if not _is_safe_member_name(n):
                    errors.append(f"unsafe archive member name: {n!r}")
                batch += 1
                if batch >= 200:
                    task.advance(batch)
                    batch = 0
            if batch:
                task.advance(batch)

            # Determine the single run_id prefix.
            run_ids = sorted(
                {PurePosixPath(n).parts[0] for n in names if _is_safe_member_name(n) and PurePosixPath(n).parts}
            )
            if len(run_ids) != 1:
                errors.append(f"expected exactly 1 run_id prefix, found {len(run_ids)}: {run_ids}")
                return sorted(errors)

            run_id = run_ids[0]
            allow_dirs = set(_ALLOWLIST_DIRS)

            # Enforce allowlist.
            for n in sorted(names):
                if not _is_safe_member_name(n):
                    continue
                p = PurePosixPath(n)
                if not p.parts or p.parts[0] != run_id:
                    errors.append(f"member not under run_id '{run_id}': {n}")
                    continue
                if len(p.parts) == 1:
                    continue  # root dir entry
                top = p.parts[1]
                if top in allow_dirs:
                    continue
                if top == _REGISTRY_DIR:
                    # Allow only registry dir and known files.
                    if len(p.parts) == 2:
                        continue
                    if len(p.parts) == 3 and p.parts[2] in {_RUN_ENTRY_JSON, _BUNDLE_MANIFEST_CSV}:
                        continue
                errors.append(f"disallowed path: {n}")

            run_entry_path = f"{run_id}/{_REGISTRY_DIR}/{_RUN_ENTRY_JSON}"
            manifest_path = f"{run_id}/{_REGISTRY_DIR}/{_BUNDLE_MANIFEST_CSV}"

            try:
                run_entry_f = tf.extractfile(run_entry_path)
            except KeyError:
                run_entry_f = None
            if run_entry_f is None:
                errors.append(f"missing {run_entry_path}")
            else:
                try:
                    json.loads(run_entry_f.read().decode("utf-8"))
                except Exception as e:
                    errors.append(f"invalid JSON: {run_entry_path}: {type(e).__name__}")

            try:
                manifest_f = tf.extractfile(manifest_path)
            except KeyError:
                manifest_f = None
            if manifest_f is None:
                errors.append(f"missing {manifest_path}")
                return sorted(errors)

            try:
                manifest_text = manifest_f.read().decode("utf-8")
            except Exception as e:
                errors.append(f"unable to read manifest: {manifest_path}: {type(e).__name__}")
                return sorted(errors)

            # Parse manifest entries.
            manifest_entries: dict[str, tuple[int, str]] = {}
            reader = csv.DictReader(io.StringIO(manifest_text))
            if list(reader.fieldnames or []) != _MANIFEST_HEADER:
                errors.append(f"invalid manifest header: {manifest_path}")
                return sorted(errors)

            for row in reader:
                p = row.get("path")
                size_s = row.get("size")
                sha = row.get("sha256")
                if not isinstance(p, str) or not p:
                    errors.append(f"invalid manifest row (missing path): {manifest_path}")
                    continue
                if p == manifest_path:
                    errors.append(f"manifest must not include itself: {manifest_path}")
                    continue
                try:
                    size = int(size_s or "")
                except ValueError:
                    errors.append(f"invalid manifest size for {p}: {size_s!r}")
                    continue
                if not isinstance(sha, str) or len(sha) != 64:
                    errors.append(f"invalid manifest sha256 for {p}")
                    continue
                manifest_entries[p] = (size, sha)

            # Determine regular file members to verify (excluding the manifest itself).
            actual_files: dict[str, tarfile.TarInfo] = {}
            for m in members:
                if not _is_safe_member_name(m.name):
                    continue
                if m.isfile():
                    if m.name == manifest_path:
                        continue
                    actual_files[m.name] = m
                elif m.isdir():
                    continue
                else:
                    errors.append(f"unsupported member type: {m.name}")

            if sorted(actual_files) != sorted(manifest_entries):
                missing = sorted(set(actual_files) - set(manifest_entries))
                extra = sorted(set(manifest_entries) - set(actual_files))
                if missing:
                    errors.append(f"files missing from manifest: {missing}")
                if extra:
                    errors.append(f"manifest references missing files: {extra}")
                return sorted(errors)

            with progress.phase("bundle: verify sha256"):
                task = progress.task("bundle: verify sha256", total=len(actual_files), unit="files")
                for path in sorted(actual_files):
                    expected_size, expected_sha = manifest_entries[path]
                    m = actual_files[path]
                    if int(m.size) != int(expected_size):
                        errors.append(f"size mismatch: {path}: expected {expected_size}, got {m.size}")
                        task.advance(1)
                        continue
                    f = tf.extractfile(m)
                    if f is None:
                        errors.append(f"unable to extract: {path}")
                        task.advance(1)
                        continue
                    actual_sha = _sha256_stream(f)
                    if actual_sha != expected_sha:
                        errors.append(f"sha256 mismatch: {path}")
                    task.advance(1)

    return sorted(errors)
