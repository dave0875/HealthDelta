from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import shutil
import zipfile
from pathlib import Path


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_zip_bytes(zip_path: Path) -> str:
    h = hashlib.sha256()
    with zip_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _count_xml_record_estimate(xml_path: Path) -> int:
    count = 0
    with xml_path.open("rb") as f:
        for line in f:
            count += line.count(b"<Record")
    return count


@dataclasses.dataclass(frozen=True)
class InputResolution:
    kind: str  # "zip" | "dir"
    input_path: Path
    export_xml_path: Path | None
    clinical_json_paths: list[Path]


def _resolve_input(input_path: Path) -> InputResolution:
    if input_path.is_file():
        if input_path.suffix.lower() != ".zip" or not zipfile.is_zipfile(input_path):
            raise ValueError(f"--input must be a .zip file or a directory: {input_path}")
        return InputResolution(kind="zip", input_path=input_path, export_xml_path=None, clinical_json_paths=[])

    if not input_path.is_dir():
        raise ValueError(f"--input must be a .zip file or a directory: {input_path}")

    candidates = [
        input_path / "export.xml",
        input_path / "apple_health_export" / "export.xml",
    ]
    export_xml = next((p for p in candidates if p.exists()), None)
    if export_xml is None:
        raise ValueError(f"Unpacked export directory must contain export.xml: {input_path}")

    clinical_json_paths = sorted([p for p in input_path.rglob("*.json") if p.is_file()])
    return InputResolution(
        kind="dir",
        input_path=input_path,
        export_xml_path=export_xml,
        clinical_json_paths=clinical_json_paths,
    )


def _compute_run_id_for_directory(*, input_root: Path, export_xml: Path, clinical_json_paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in [export_xml, *clinical_json_paths]:
        rel = p.relative_to(input_root).as_posix().encode("utf-8", errors="strict")
        h.update(rel)
        h.update(b"\0")
        h.update(_sha256_file(p).encode("ascii"))
        h.update(b"\n")
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
    resolved = _resolve_input(Path(input_path))
    staging_root_path = Path(staging_root)
    started_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    if resolved.kind == "zip":
        computed = _sha256_zip_bytes(resolved.input_path)
        run_id = run_id_override or computed
        run_dir = staging_root_path / run_id
        source_dir = run_dir / "source"
        unpacked_dir = source_dir / "unpacked"

        run_dir.mkdir(parents=True, exist_ok=True)
        source_dir.mkdir(parents=True, exist_ok=True)
        unpacked_dir.mkdir(parents=True, exist_ok=True)

        staged_zip = source_dir / "export.zip"
        shutil.copy2(resolved.input_path, staged_zip)

        export_xml_rel = None
        clinical_rels: list[str] = []
        with zipfile.ZipFile(resolved.input_path) as zf:
            for member in sorted(zf.namelist()):
                if member.endswith("/"):
                    continue
                lower = member.lower()
                if lower.endswith("export.xml") or lower.endswith(".json"):
                    out_path = unpacked_dir / member
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, out_path.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
                    if lower.endswith("export.xml") and export_xml_rel is None:
                        export_xml_rel = (Path("source") / "unpacked" / member).as_posix()
                    if lower.endswith(".json"):
                        clinical_rels.append((Path("source") / "unpacked" / member).as_posix())

        if export_xml_rel is None:
            raise ValueError("export.zip did not contain export.xml")

        export_xml_path = run_dir / export_xml_rel
        clinical_paths = [run_dir / p for p in clinical_rels]

        files = []
        for p in [staged_zip, export_xml_path, *clinical_paths]:
            if not p.exists():
                continue
            rel = p.relative_to(run_dir).as_posix()
            files.append({"path": rel, "size_bytes": p.stat().st_size, "sha256": _sha256_file(p)})

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
            "clinical_json": clinical_rels,
        }

        _write_json(run_dir / "manifest.json", manifest)
        _write_json(run_dir / "layout.json", layout)
        return run_dir

    export_xml = resolved.export_xml_path
    if export_xml is None:
        raise AssertionError("resolved.export_xml_path must be set for dir inputs")

    computed = _compute_run_id_for_directory(
        input_root=resolved.input_path,
        export_xml=export_xml,
        clinical_json_paths=resolved.clinical_json_paths,
    )
    run_id = run_id_override or computed
    run_dir = staging_root_path / run_id
    source_dir = run_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    staged_export_xml = source_dir / "export.xml"
    shutil.copy2(export_xml, staged_export_xml)

    staged_clinical_dir = source_dir / "clinical"
    staged_clinical_dir.mkdir(parents=True, exist_ok=True)

    clinical_rels: list[str] = []
    for p in resolved.clinical_json_paths:
        rel = p.relative_to(resolved.input_path).as_posix()
        out_path = staged_clinical_dir / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out_path)
        clinical_rels.append((out_path.relative_to(run_dir)).as_posix())

    files = []
    for p in [staged_export_xml, *[run_dir / r for r in clinical_rels]]:
        rel = p.relative_to(run_dir).as_posix()
        files.append({"path": rel, "size_bytes": p.stat().st_size, "sha256": _sha256_file(p)})

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
        "clinical_json": clinical_rels,
    }

    _write_json(run_dir / "manifest.json", manifest)
    _write_json(run_dir / "layout.json", layout)
    return run_dir
