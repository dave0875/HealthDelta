from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from healthdelta.export_layout import resolve_export_layout
from healthdelta.progress import progress


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_zip_bytes(zip_path: Path) -> str:
    h = hashlib.sha256()
    task = progress.task("Hash export.zip bytes", total=zip_path.stat().st_size, unit="bytes")
    with zip_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
            task.advance(len(chunk))
    return h.hexdigest()


def _copy_file_with_progress(*, src: Path, dst: Path, label: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    total = src.stat().st_size
    task = progress.task(label, total=total, unit="bytes")
    with src.open("rb") as fsrc, dst.open("wb") as fdst:
        for chunk in iter(lambda: fsrc.read(1024 * 1024), b""):
            fdst.write(chunk)
            task.advance(len(chunk))


def _count_xml_record_estimate(xml_path: Path) -> int:
    count = 0
    with xml_path.open("rb") as f:
        for line in f:
            count += line.count(b"<Record")
    return count


def _count_newlines(path: Path) -> int:
    count = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            count += chunk.count(b"\n")
    return count


@dataclasses.dataclass(frozen=True)
class InputResolution:
    kind: str  # "zip" | "dir"
    input_path: Path
    export_xml_path: Path | None
    export_cda_path: Path | None
    clinical_json_paths: list[Path]


def _resolve_input(input_path: Path) -> InputResolution:
    if input_path.is_file():
        if input_path.suffix.lower() != ".zip" or not zipfile.is_zipfile(input_path):
            raise ValueError(f"--input must be a .zip file or a directory: {input_path}")
        return InputResolution(kind="zip", input_path=input_path, export_xml_path=None, export_cda_path=None, clinical_json_paths=[])

    if not input_path.is_dir():
        raise ValueError(f"--input must be a .zip file or a directory: {input_path}")

    layout = resolve_export_layout(input_path)
    export_root = input_path if layout.export_root_rel == "." else (input_path / layout.export_root_rel)
    export_xml = export_root / layout.export_xml_rel
    export_cda = export_root / layout.export_cda_rel if isinstance(layout.export_cda_rel, str) else None

    clinical_json_paths: list[Path] = []
    if isinstance(layout.clinical_dir_rel, str):
        clinical_root = export_root / layout.clinical_dir_rel
        clinical_json_paths = sorted([p for p in clinical_root.rglob("*.json") if p.is_file()])
    return InputResolution(
        kind="dir",
        input_path=input_path,
        export_xml_path=export_xml,
        export_cda_path=export_cda,
        clinical_json_paths=clinical_json_paths,
    )


def _compute_run_id_for_directory(*, input_root: Path, export_xml: Path, clinical_json_paths: list[Path]) -> str:
    h = hashlib.sha256()
    files = [export_xml, *clinical_json_paths]
    task = progress.task("Derive run_id (hash inputs)", total=len(files), unit="files")
    for p in files:
        rel = p.relative_to(input_root).as_posix().encode("utf-8", errors="strict")
        h.update(rel)
        h.update(b"\0")
        h.update(_sha256_file(p).encode("ascii"))
        h.update(b"\n")
        task.advance(1)
    return h.hexdigest()


def _redacted_input(kind: str) -> dict:
    return {
        "path_redacted": True,
        "kind": kind,
        "path_hint": "export.zip" if kind == "zip" else "export_dir",
    }


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ingest_to_staging(*, input_path: str, staging_root: str = "data/staging", run_id_override: str | None = None) -> Path:
    with progress.phase("ingest: resolve input"):
        resolved = _resolve_input(Path(input_path))
    staging_root_path = Path(staging_root)
    started_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    if resolved.kind == "zip":
        with progress.phase("ingest: compute run_id"):
            computed = _sha256_zip_bytes(resolved.input_path)
        run_id = run_id_override or computed
        run_dir = staging_root_path / run_id
        source_dir = run_dir / "source"
        unpacked_dir = source_dir / "unpacked"

        with progress.phase("ingest: stage directories"):
            run_dir.mkdir(parents=True, exist_ok=True)
            source_dir.mkdir(parents=True, exist_ok=True)
            unpacked_dir.mkdir(parents=True, exist_ok=True)

        staged_zip = source_dir / "export.zip"
        with progress.phase("ingest: stage export.zip"):
            _copy_file_with_progress(src=resolved.input_path, dst=staged_zip, label="Copy export.zip")

        export_xml_rel = None
        export_cda_rel: str | None = None
        clinical_rels: list[str] = []
        with progress.phase("ingest: extract zip members"):
            with zipfile.ZipFile(resolved.input_path) as zf:
                members = [m for m in sorted(zf.namelist()) if not m.endswith("/")]

                def include_member(m: str) -> bool:
                    lower = m.lower()
                    if lower.endswith("export.xml") or lower.endswith("export_cda.xml"):
                        return True
                    if lower.endswith(".json"):
                        return "/clinical_records/" in lower or "/clinical-records/" in lower
                    return False

                selected = [m for m in members if include_member(m)]
                task = progress.task("Extract staged files", total=len(selected), unit="files")

                for member in selected:
                    lower = member.lower()
                    out_path = unpacked_dir / member
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, out_path.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
                    if lower.endswith("export.xml") and export_xml_rel is None:
                        export_xml_rel = (Path("source") / "unpacked" / member).as_posix()
                    if lower.endswith("export_cda.xml") and export_cda_rel is None:
                        export_cda_rel = (Path("source") / "unpacked" / member).as_posix()
                    if lower.endswith(".json"):
                        clinical_rels.append((Path("source") / "unpacked" / member).as_posix())
                    task.advance(1)

        if export_xml_rel is None:
            raise ValueError("export.zip did not contain export.xml")

        export_xml_path = run_dir / export_xml_rel
        export_cda_path = run_dir / export_cda_rel if export_cda_rel is not None else None
        clinical_paths = [run_dir / p for p in clinical_rels]

        files = []
        with progress.phase("ingest: hash staged files"):
            to_hash = [p for p in [staged_zip, export_xml_path, export_cda_path, *clinical_paths] if p and p.exists()]
            task = progress.task("Hash staged files", total=len(to_hash), unit="files")
            for p in to_hash:
                rel = p.relative_to(run_dir).as_posix()
                files.append({"path": rel, "size_bytes": p.stat().st_size, "sha256": _sha256_file(p)})
                task.advance(1)

        with progress.phase("ingest: write manifests"):
            manifest = {
                "run_id": run_id,
                "input": _redacted_input("zip"),
                "files": sorted(files, key=lambda x: x["path"]),
                "counts": {
                    "xml_record_count_estimate": _count_xml_record_estimate(export_xml_path),
                    "clinical_json_file_count": len(clinical_paths),
                },
                "timestamps": {
                    "started_at": started_at,
                    "finished_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
                },
                "determinism": {
                    "run_id_derivation": "sha256(export.zip bytes)" if run_id_override is None else "override (incremental pipeline run_id)",
                    "stable_fields": ["run_id", "files[*].sha256", "files[*].size_bytes", "counts.*"],
                    "time_fields": ["timestamps.*"],
                },
            }

            layout = {
                "run_id": run_id,
                "export_xml": export_xml_rel,
                "export_cda_xml": export_cda_rel,
                "clinical_json": clinical_rels,
            }

            _write_json(run_dir / "manifest.json", manifest)
            _write_json(run_dir / "layout.json", layout)
        return run_dir

    export_xml = resolved.export_xml_path
    if export_xml is None:
        raise AssertionError("resolved.export_xml_path must be set for dir inputs")

    with progress.phase("ingest: compute run_id"):
        computed = _compute_run_id_for_directory(
            input_root=resolved.input_path,
            export_xml=export_xml,
            clinical_json_paths=resolved.clinical_json_paths,
        )
    run_id = run_id_override or computed
    run_dir = staging_root_path / run_id
    source_dir = run_dir / "source"
    with progress.phase("ingest: stage directories"):
        source_dir.mkdir(parents=True, exist_ok=True)

    staged_export_xml = source_dir / "export.xml"
    with progress.phase("ingest: stage export.xml"):
        _copy_file_with_progress(src=export_xml, dst=staged_export_xml, label="Copy export.xml")

    staged_unpacked_dir = source_dir / "unpacked"
    staged_unpacked_dir.mkdir(parents=True, exist_ok=True)

    staged_export_cda = None
    if resolved.export_cda_path is not None and resolved.export_cda_path.exists():
        staged_export_cda = staged_unpacked_dir / "export_cda.xml"
        with progress.phase("ingest: stage export_cda.xml"):
            _copy_file_with_progress(src=resolved.export_cda_path, dst=staged_export_cda, label="Copy export_cda.xml")

    staged_clinical_root = source_dir / "clinical" / "clinical-records"
    staged_clinical_root.mkdir(parents=True, exist_ok=True)

    clinical_rels: list[str] = []
    with progress.phase("ingest: stage clinical json"):
        task = progress.task("Copy clinical JSON", total=len(resolved.clinical_json_paths), unit="files")
        for p in resolved.clinical_json_paths:
            # Canonicalize to stable staging paths regardless of input directory variant.
            out_path = staged_clinical_root / p.name
            out_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, out_path)
            clinical_rels.append((out_path.relative_to(run_dir)).as_posix())
            task.advance(1)

    files = []
    with progress.phase("ingest: hash staged files"):
        to_hash = [p for p in [staged_export_xml, staged_export_cda, *[run_dir / r for r in clinical_rels]] if p and p.exists()]
        task = progress.task("Hash staged files", total=len(to_hash), unit="files")
        for p in to_hash:
            rel = p.relative_to(run_dir).as_posix()
            files.append({"path": rel, "size_bytes": p.stat().st_size, "sha256": _sha256_file(p)})
            task.advance(1)

    with progress.phase("ingest: write manifests"):
        manifest = {
            "run_id": run_id,
            "input": _redacted_input("dir"),
            "files": sorted(files, key=lambda x: x["path"]),
            "counts": {
                "xml_record_count_estimate": _count_xml_record_estimate(staged_export_xml),
                "clinical_json_file_count": len(clinical_rels),
            },
            "timestamps": {
                "started_at": started_at,
                "finished_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            },
            "determinism": {
                "run_id_derivation": "sha256(relpath + sha256(bytes)) over export.xml + clinical jsons"
                if run_id_override is None
                else "override (incremental pipeline run_id)",
                "stable_fields": ["run_id", "files[*].sha256", "files[*].size_bytes", "counts.*"],
                "time_fields": ["timestamps.*"],
            },
        }

        layout = {
            "run_id": run_id,
            "export_xml": staged_export_xml.relative_to(run_dir).as_posix(),
            "export_cda_xml": staged_export_cda.relative_to(run_dir).as_posix() if staged_export_cda is not None else None,
            "clinical_json": clinical_rels,
        }

        _write_json(run_dir / "manifest.json", manifest)
        _write_json(run_dir / "layout.json", layout)
    return run_dir


def _compute_run_id_for_ios_export(*, input_dir: Path, required_paths: list[Path]) -> str:
    h = hashlib.sha256()
    task = progress.task("Derive run_id (hash iOS inputs)", total=len(required_paths), unit="files")
    for p in required_paths:
        rel = p.relative_to(input_dir).as_posix().encode("utf-8", errors="strict")
        h.update(rel)
        h.update(b"\0")
        h.update(_sha256_file(p).encode("ascii"))
        h.update(b"\n")
        task.advance(1)
    return h.hexdigest()


def ingest_ios_to_staging(*, input_dir: str, staging_root: str = "data/staging") -> Path:
    with progress.phase("ingest(ios): resolve input"):
        src = Path(input_dir)
        if not src.is_dir():
            raise ValueError(f"--input must be a directory: {src}")

        ios_manifest = src / "manifest.json"
        observations = src / "ndjson" / "observations.ndjson"
        missing = [p for p in [ios_manifest, observations] if not p.exists()]
        if missing:
            raise ValueError(f"iOS export dir missing required file(s): {', '.join(str(p) for p in missing)}")

    with progress.phase("ingest(ios): compute run_id"):
        run_id = _compute_run_id_for_ios_export(input_dir=src, required_paths=[ios_manifest, observations])
    run_dir = Path(staging_root) / run_id

    staged_ios_manifest = run_dir / "source" / "ios" / "manifest.json"
    staged_observations = run_dir / "ndjson" / "observations.ndjson"
    staged_ios_manifest.parent.mkdir(parents=True, exist_ok=True)
    staged_observations.parent.mkdir(parents=True, exist_ok=True)

    with progress.phase("ingest(ios): stage files"):
        _copy_file_with_progress(src=ios_manifest, dst=staged_ios_manifest, label="Copy iOS manifest.json")
        _copy_file_with_progress(src=observations, dst=staged_observations, label="Copy observations.ndjson")

    files: list[dict[str, object]] = []
    with progress.phase("ingest(ios): hash staged files"):
        to_hash = [staged_ios_manifest, staged_observations]
        task = progress.task("Hash staged files", total=len(to_hash), unit="files")
        for p in to_hash:
            rel = p.relative_to(run_dir).as_posix()
            files.append({"path": rel, "size_bytes": p.stat().st_size, "sha256": _sha256_file(p)})
            task.advance(1)

    with progress.phase("ingest(ios): write manifest"):
        manifest = {
            "run_id": run_id,
            "input": {"path_redacted": True, "kind": "ios", "path_hint": "ios_export_dir"},
            "files": sorted(files, key=lambda x: x["path"]),
            "counts": {
                "ndjson_observations_row_count": _count_newlines(staged_observations),
            },
            "determinism": {
                "run_id_derivation": "sha256(relpath + sha256(bytes)) over iOS manifest + observations.ndjson",
                "stable_fields": ["run_id", "files[*].sha256", "files[*].size_bytes", "counts.*"],
                "time_fields": [],
            },
        }

        _write_json(run_dir / "manifest.json", manifest)
    return run_dir
