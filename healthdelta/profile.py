from __future__ import annotations

import csv
import hashlib
import json
import re
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from healthdelta.export_layout import resolve_export_layout
from healthdelta.progress import progress


FHIR_CANONICAL_MAPPING_RESOURCE_TYPES: tuple[str, ...] = (
    "Observation",
    "DocumentReference",
    "MedicationRequest",
    "MedicationStatement",
    "MedicationDispense",
    "Condition",
    "AllergyIntolerance",
    "Immunization",
    "Encounter",
    "Procedure",
    "DiagnosticReport",
)


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent)) as tf:
        tmp = Path(tf.name)
        tf.write(text)
        if not text.endswith("\n"):
            tf.write("\n")
    tmp.replace(path)


def _write_json(path: Path, obj: object) -> None:
    _write_text_atomic(path, json.dumps(obj, indent=2, sort_keys=True) + "\n")


def _write_csv(path: Path, *, header: list[str], rows: Iterable[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent), newline="") as tf:
        tmp = Path(tf.name)
        w = csv.writer(tf, lineterminator="\n")
        w.writerow(header)
        for row in rows:
            w.writerow(["" if v is None else str(v) for v in row])
    tmp.replace(path)


def _safe_relpath(p: Path) -> str:
    # Ensure we never emit absolute paths.
    if p.is_absolute():
        return p.name
    return p.as_posix()


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _localname(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


@dataclass(frozen=True)
class FileInfo:
    relpath: str
    size_bytes: int


def _walk_files(root: Path) -> list[FileInfo]:
    files: list[FileInfo] = []
    task = progress.task("profile: scan files", unit="files")
    batch = 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = _safe_relpath(p.relative_to(root))
        files.append(FileInfo(relpath=rel, size_bytes=p.stat().st_size))
        batch += 1
        if batch >= 200:
            task.advance(batch)
            batch = 0
    if batch:
        task.advance(batch)
    files.sort(key=lambda x: x.relpath)
    return files


def _counts_by_ext(files: list[FileInfo]) -> list[tuple[str, int]]:
    c: Counter[str] = Counter()
    for f in files:
        ext = Path(f.relpath).suffix.casefold()
        c[ext] += 1
    items = list(c.items())
    items.sort(key=lambda kv: (-kv[1], kv[0]))
    return items


def _top_files(files: list[FileInfo], k: int) -> list[FileInfo]:
    if k <= 0:
        return []
    items = sorted(files, key=lambda x: (-x.size_bytes, x.relpath))
    return items[:k]


_RECORD_TYPE_RE = re.compile(br"<Record\b[^>]*\btype=\"([^\"]+)\"")


def _count_healthkit_record_types(export_xml: Path) -> list[tuple[str, int]]:
    """
    Streaming-safe scan for HealthKit Record type counts.
    Fast heuristic: counts occurrences of `<Record ... type="...">` without building a DOM.
    """
    if not export_xml.exists():
        return []

    counts: Counter[str] = Counter()
    carry = b""
    carry_keep = 8192
    task = progress.task("profile: scan export.xml", total=export_xml.stat().st_size, unit="bytes")
    with export_xml.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            data = carry + chunk
            cutoff = max(0, len(data) - carry_keep)
            for m in _RECORD_TYPE_RE.finditer(data):
                if m.start() >= cutoff:
                    continue
                t = m.group(1).decode("utf-8", errors="replace").strip()
                if t:
                    counts[t] += 1
            carry = data[-carry_keep:] if len(data) > carry_keep else data
            task.advance(len(chunk))
    # Final pass for remaining carry (safe; no further overlaps).
    for m in _RECORD_TYPE_RE.finditer(carry):
        t = m.group(1).decode("utf-8", errors="replace").strip()
        if t:
            counts[t] += 1

    items = list(counts.items())
    items.sort(key=lambda kv: (-kv[1], kv[0]))
    return items


_FHIR_RESOURCE_TYPE_RE = re.compile(br"\"resourceType\"\s*:\s*\"([A-Za-z][A-Za-z0-9]+)\"")

_SENSITIVE_FIELD_STRATEGIES: dict[str, str] = {
    "name": "remove_or_tokenize",
    "birthDate": "coarsen_or_remove",
    "address": "remove",
    "telecom": "remove",
    "identifier": "tokenize_or_remove",
    "display": "redact_free_text",
    "div": "redact_narrative",
    "text": "redact_narrative",
    "note": "redact_narrative",
    "valueString": "redact_free_text",
}


def _extract_fhir_resource_type(path: Path, *, max_bytes: int = 64 * 1024) -> str | None:
    # Read a bounded prefix and only extract resourceType.
    with path.open("rb") as f:
        head = f.read(max_bytes)
    m = _FHIR_RESOURCE_TYPE_RE.search(head)
    if not m:
        return None
    rt = m.group(1).decode("utf-8", errors="replace").strip()
    return rt or None


def _collect_schema_paths(obj: object, prefix: str, out: set[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if not isinstance(key, str) or not key:
                continue
            path = f"{prefix}.{key}" if prefix else key
            out.add(path)
            _collect_schema_paths(value, path, out)
        return
    if isinstance(obj, list):
        list_path = f"{prefix}[]" if prefix else "[]"
        out.add(list_path)
        for item in obj:
            _collect_schema_paths(item, list_path, out)
        return


def _count_clinical_resource_types(
    clinical_dir: Path, *, sample_json: int
) -> tuple[list[tuple[str, int]], dict[str, int], dict[str, list[tuple[str, int]]], dict[str, object]]:
    """
    Counts FHIR resourceType across clinical JSON files. Deterministic sampling:
    - files are sorted by relative path
    - only the first N files are scanned when sample_json > 0
    """
    if not clinical_dir.exists() or not clinical_dir.is_dir():
        return [], {"total_files": 0, "sampled_files": 0}, {}, {"sensitive_fields": [], "sensitive_paths_observed": []}

    json_files = sorted([p for p in clinical_dir.rglob("*.json") if p.is_file()], key=lambda p: p.relative_to(clinical_dir).as_posix())
    total = len(json_files)
    if sample_json > 0:
        json_files = json_files[:sample_json]
    sampled = len(json_files)

    counts: Counter[str] = Counter()
    schema_by_resource: dict[str, Counter[str]] = {}
    sensitive_paths: list[dict[str, str]] = []
    observed_sensitive: set[str] = set()
    task = progress.task("profile: scan clinical JSON", total=len(json_files), unit="files")
    for p in json_files:
        rt = _extract_fhir_resource_type(p)
        data_obj: object | None = None
        try:
            data_obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            data_obj = None
        if rt:
            counts[rt] += 1
        if isinstance(data_obj, dict):
            paths: set[str] = set()
            _collect_schema_paths(data_obj, "", paths)
            resource = rt or "Unknown"
            bucket = schema_by_resource.setdefault(resource, Counter())
            for path in paths:
                bucket[path] += 1
                leaf = path.split(".")[-1].replace("[]", "")
                if leaf in _SENSITIVE_FIELD_STRATEGIES:
                    observed_sensitive.add(leaf)
                    sensitive_paths.append(
                        {
                            "resourceType": resource,
                            "path": path,
                            "field": leaf,
                            "strategy": _SENSITIVE_FIELD_STRATEGIES[leaf],
                        }
                    )
        task.advance(1)

    items = list(counts.items())
    items.sort(key=lambda kv: (-kv[1], kv[0]))
    schema_out: dict[str, list[tuple[str, int]]] = {}
    for resource, resource_counts in schema_by_resource.items():
        pairs = list(resource_counts.items())
        pairs.sort(key=lambda kv: (-kv[1], kv[0]))
        schema_out[resource] = pairs

    sensitive_fields_out = []
    for field in sorted(_SENSITIVE_FIELD_STRATEGIES.keys()):
        resource_types = sorted({x["resourceType"] for x in sensitive_paths if x["field"] == field})
        sensitive_fields_out.append(
            {
                "field": field,
                "strategy": _SENSITIVE_FIELD_STRATEGIES[field],
                "observed": field in observed_sensitive,
                "observed_resource_types": resource_types,
            }
        )
    sensitive_paths.sort(key=lambda x: (x["resourceType"], x["path"], x["field"]))
    sensitive_obj = {"sensitive_fields": sensitive_fields_out, "sensitive_paths_observed": sensitive_paths}
    return items, {"total_files": total, "sampled_files": sampled}, schema_out, sensitive_obj


_CDA_TAG_RE = re.compile(br"<\s*([A-Za-z_][A-Za-z0-9_.:-]*)")


def _count_cda_tags(export_cda_xml: Path, *, top_n: int = 50) -> list[tuple[str, int]]:
    """
    Streaming-safe tag name counter for CDA XML (start tags only).
    Counts local tag names (drops namespace prefix like `hl7:`).
    """
    if not export_cda_xml.exists():
        return []

    counts: Counter[str] = Counter()
    carry = b""
    carry_keep = 8192
    task = progress.task("profile: scan export_cda.xml", total=export_cda_xml.stat().st_size, unit="bytes")
    with export_cda_xml.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            data = carry + chunk
            cutoff = max(0, len(data) - carry_keep)
            for m in _CDA_TAG_RE.finditer(data):
                if m.start() >= cutoff:
                    continue
                raw = m.group(1)
                if not raw or raw.startswith((b"/", b"!", b"?")):
                    continue
                tag = raw.decode("utf-8", errors="replace")
                tag = tag.split(":", 1)[-1]
                if tag:
                    counts[tag] += 1
            carry = data[-carry_keep:] if len(data) > carry_keep else data
            task.advance(len(chunk))
    for m in _CDA_TAG_RE.finditer(carry):
        raw = m.group(1)
        if not raw or raw.startswith((b"/", b"!", b"?")):
            continue
        tag = raw.decode("utf-8", errors="replace")
        tag = tag.split(":", 1)[-1]
        if tag:
            counts[tag] += 1

    items = list(counts.items())
    items.sort(key=lambda kv: (-kv[1], kv[0]))
    return items[: max(0, top_n)]


def _count_cda_sections(export_cda_xml: Path) -> list[dict[str, object]]:
    if not export_cda_xml.exists():
        return []

    counts: Counter[tuple[str | None, str | None, str | None]] = Counter()
    task = progress.task("profile: scan CDA sections", unit="sections")
    for _event, el in ET.iterparse(str(export_cda_xml), events=("end",)):
        if _localname(el.tag) != "section":
            continue
        section_code: str | None = None
        section_display: str | None = None
        section_title: str | None = None
        for child in list(el):
            ln = _localname(child.tag)
            if ln == "code":
                raw_code = child.attrib.get("code")
                raw_display = child.attrib.get("displayName")
                section_code = raw_code.strip() if isinstance(raw_code, str) and raw_code.strip() else None
                section_display = raw_display.strip() if isinstance(raw_display, str) and raw_display.strip() else None
            elif ln == "title":
                raw_title = "".join(child.itertext()).strip()
                section_title = raw_title or None
        counts[(section_code, section_display, section_title)] += 1
        el.clear()
        task.advance(1)

    rows: list[dict[str, object]] = []
    for (section_code, section_display, section_title), count in sorted(
        counts.items(),
        key=lambda item: (
            -(item[1]),
            item[0][0] or "",
            item[0][1] or "",
            item[0][2] or "",
        ),
    ):
        rows.append(
            {
                "section_code": section_code,
                "section_display": section_display,
                "section_title": section_title,
                "count": count,
            }
        )
    return rows


def _stable_profile_id(files: list[FileInfo]) -> str:
    """
    Deterministic profile id derived from file list (relpath + size only).
    Intentionally does NOT hash file contents to keep profiling fast for multi-GB exports.
    """
    h = hashlib.sha256()
    for f in files:
        h.update(f.relpath.encode("utf-8"))
        h.update(b"\0")
        h.update(str(f.size_bytes).encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def build_export_profile(*, input_dir: str, out_dir: str, sample_json: int = 200, top_files: int = 20) -> None:
    with progress.phase("profile: init"):
        input_root = Path(input_dir)
        if not input_root.is_dir():
            raise ValueError("--input must be an unpacked export directory")

        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

    with progress.phase("profile: resolve layout"):
        layout = resolve_export_layout(input_root)
        export_root = input_root if layout.export_root_rel == "." else (input_root / layout.export_root_rel)

    with progress.phase("profile: walk files"):
        files = _walk_files(export_root)
        total_bytes = sum(f.size_bytes for f in files)

    export_xml = export_root / layout.export_xml_rel
    export_cda = export_root / layout.export_cda_rel if isinstance(layout.export_cda_rel, str) else export_root / "export_cda.xml"
    clinical_dir = export_root / layout.clinical_dir_rel if isinstance(layout.clinical_dir_rel, str) else export_root / "clinical-records"

    with progress.phase("profile: scan export.xml"):
        hk_counts = _count_healthkit_record_types(export_xml) if export_xml.exists() else []

    with progress.phase("profile: scan clinical JSON"):
        fhir_counts, fhir_meta, fhir_schema, sensitive_map = _count_clinical_resource_types(clinical_dir, sample_json=sample_json)

    with progress.phase("profile: scan export_cda.xml"):
        cda_counts = _count_cda_tags(export_cda, top_n=50) if export_cda.exists() else []
        cda_sections = _count_cda_sections(export_cda) if export_cda.exists() else []

    with progress.phase("profile: aggregate"):
        ext_counts = _counts_by_ext(files)
        top = _top_files(files, top_files)

    profile_id = _stable_profile_id(files)
    profile_obj: dict[str, object] = {
        "schema_version": 1,
        "profile_id": profile_id,
        "input": {"path_redacted": True, "kind": "export_dir"},
        "summary": {
            "export_root_rel": layout.export_root_rel,
            "file_count": len(files),
            "total_bytes": total_bytes,
            "has_export_xml": export_xml.exists(),
            "has_export_cda_xml": export_cda.exists(),
            "clinical_json_total_files": fhir_meta["total_files"],
            "clinical_json_sampled_files": fhir_meta["sampled_files"],
        },
        "top_files": [{"path": f.relpath, "size_bytes": f.size_bytes} for f in top],
        "counts_by_ext": [{"ext": ext, "count": n} for ext, n in ext_counts],
        "healthkit_record_types": [{"type": t, "count": n} for t, n in hk_counts],
        "clinical_resource_types": [{"resourceType": t, "count": n} for t, n in fhir_counts],
        "clinical_schema_keys": {
            resource: [{"path": path, "count": count} for path, count in rows]
            for resource, rows in sorted(fhir_schema.items())
        },
        "sensitive_field_map": sensitive_map,
        "cda_tag_counts": [{"tag": t, "count": n} for t, n in cda_counts],
        "determinism": {
            "notes": [
                "profile_id is derived from relpath + size only (no content hashing) for speed on large exports",
                "no absolute paths, timestamps, or payload fragments are emitted",
                "ordering is deterministic (explicit sorts; newline-terminated outputs)",
            ],
        },
    }

    with progress.phase("profile: write artifacts"):
        task = progress.task("profile: write artifacts", unit="files")

        # Write outputs (deterministic ordering/formatting).
        _write_json(out / "profile.json", profile_obj)
        task.advance(1)
        _write_json(
            out / "clinical_coverage_inventory.json",
            {
                "schema_version": 1,
                "profile_id": profile_id,
                "summary": {
                    "clinical_json_total_files": fhir_meta["total_files"],
                    "clinical_json_sampled_files": fhir_meta["sampled_files"],
                    "has_export_cda_xml": export_cda.exists(),
                    "cda_section_total": sum(int(row["count"]) for row in cda_sections),
                },
                "fhir_resource_types": [{"resourceType": t, "count": n} for t, n in fhir_counts],
                "cda_sections": cda_sections,
                "privacy": {
                    "share_safe": True,
                    "notes": [
                        "Only aggregate counts and schema-level identifiers are emitted",
                        "No names, dates of birth, identifiers, timestamps, or free-text payload fragments are included",
                    ],
                },
            },
        )
        task.advance(1)
        _write_json(
            out / "clinical_inventory.json",
            {
                "schema_version": 1,
                "profile_id": profile_id,
                "summary": {
                    "clinical_json_total_files": fhir_meta["total_files"],
                    "clinical_json_sampled_files": fhir_meta["sampled_files"],
                    "has_export_cda_xml": export_cda.exists(),
                    "cda_section_total": sum(int(row["count"]) for row in cda_sections),
                },
                "fhir_resource_types": [{"resourceType": t, "count": n} for t, n in fhir_counts],
                "cda_sections": cda_sections,
                "privacy": {
                    "share_safe": True,
                    "notes": [
                        "Only aggregate counts and schema-level identifiers are emitted",
                        "No names, dates of birth, identifiers, timestamps, or free-text payload fragments are included",
                    ],
                },
            },
        )
        task.advance(1)

        _write_csv(
            out / "files_top.csv",
            header=["size_bytes", "path"],
            rows=[[f.size_bytes, f.relpath] for f in top],
        )
        task.advance(1)
        _write_csv(
            out / "counts_by_ext.csv",
            header=["ext", "count"],
            rows=[[ext, n] for ext, n in ext_counts],
        )
        task.advance(1)
        if hk_counts:
            _write_csv(out / "healthkit_record_types.csv", header=["type", "count"], rows=[[t, n] for t, n in hk_counts])
            task.advance(1)
        if fhir_counts:
            _write_csv(
                out / "clinical_resource_types.csv",
                header=["resourceType", "count"],
                rows=[[t, n] for t, n in fhir_counts],
            )
            task.advance(1)
        if fhir_schema:
            schema_rows: list[list[object]] = []
            for resource in sorted(fhir_schema.keys()):
                for path, count in fhir_schema[resource]:
                    schema_rows.append([resource, path, count])
            _write_csv(
                out / "clinical_schema_keys.csv",
                header=["resourceType", "path", "count"],
                rows=schema_rows,
            )
            task.advance(1)
        _write_json(out / "sensitive_field_map.json", sensitive_map)
        task.advance(1)
        if cda_counts:
            _write_csv(out / "cda_tag_counts.csv", header=["tag", "count"], rows=[[t, n] for t, n in cda_counts])
            task.advance(1)

    md_lines: list[str] = []
    md_lines.append("# Export Profile")
    md_lines.append("")
    md_lines.append("## Summary")
    md_lines.append(f"- file_count: {len(files)}")
    md_lines.append(f"- total_bytes: {total_bytes}")
    md_lines.append(f"- export.xml: {'present' if export_xml.exists() else 'missing'}")
    md_lines.append(f"- export_cda.xml: {'present' if export_cda.exists() else 'missing'}")
    md_lines.append(f"- clinical JSON files: {fhir_meta['total_files']} (sampled {fhir_meta['sampled_files']})")
    md_lines.append("")

    md_lines.append("## Next Steps")
    md_lines.append("- Preferred one-command operator path (share-safe default):")
    md_lines.append("  - `healthdelta run all --input <export_dir> --out data --mode share`")
    if export_xml.exists():
        md_lines.append("- Pipeline-only (ingest -> identity -> optional deid):")
        md_lines.append("  - share-safe: `healthdelta pipeline run --input <export_dir> --out data --mode share`")
        md_lines.append("  - local-only: `healthdelta pipeline run --input <export_dir> --out data --mode local`")
    else:
        md_lines.append("- `export.xml` is missing; validate you selected the correct export root (Apple Health exports must include `export.xml`).")
    if export_cda.exists():
        md_lines.append("- ClinicalDocument detected (`export_cda.xml` present): use `--mode share` for de-identified outputs before sharing.")
    if fhir_meta["total_files"] > 0:
        md_lines.append("- FHIR clinical JSON detected: use `--mode share` before sharing outputs with others.")
    md_lines.append("")

    md_lines.append("## Top Files")
    if top:
        for f in top[: min(len(top), 10)]:
            md_lines.append(f"- {f.size_bytes}  {f.relpath}")
    else:
        md_lines.append("- (none)")
    md_lines.append("")

    md_lines.append("## Counts By Extension")
    for ext, n in ext_counts[: min(len(ext_counts), 15)]:
        md_lines.append(f"- {ext or '(none)'}: {n}")
    md_lines.append("")

    if hk_counts:
        md_lines.append("## HealthKit Record Types (export.xml)")
        for t, n in hk_counts[: min(len(hk_counts), 15)]:
            md_lines.append(f"- {t}: {n}")
        md_lines.append("")

    if fhir_counts:
        md_lines.append("## Clinical Resource Types (clinical-records/*.json)")
        for t, n in fhir_counts[: min(len(fhir_counts), 15)]:
            md_lines.append(f"- {t}: {n}")
        md_lines.append("")

    if fhir_schema:
        md_lines.append("## Clinical Schema Keys (sampled JSON)")
        for resource in sorted(fhir_schema.keys())[:10]:
            md_lines.append(f"- {resource}:")
            for path, count in fhir_schema[resource][:8]:
                md_lines.append(f"  - {path} ({count})")
        md_lines.append("")

    md_lines.append("## Sensitive Field Redaction Strategy")
    for row in sensitive_map["sensitive_fields"]:
        status = "observed" if row.get("observed") else "not observed"
        md_lines.append(f"- {row['field']}: {row['strategy']} ({status})")
    md_lines.append("")

    if cda_counts:
        md_lines.append("## CDA Tag Counts (export_cda.xml, top)")
        for t, n in cda_counts[: min(len(cda_counts), 15)]:
            md_lines.append(f"- {t}: {n}")
        md_lines.append("")

    md_lines.append("## Privacy")
    md_lines.append("- Output is share-safe: no names, DOB, identifiers, free-text payload fragments, or timestamps.")
    md_lines.append("- Only schema-level strings (HK `type`, FHIR `resourceType`, CDA tag names) and aggregate counts are emitted.")

    with progress.phase("profile: write markdown"):
        task_md = progress.task("profile: write markdown", total=1, unit="files")
        _write_text_atomic(out / "profile.md", "\n".join(md_lines) + "\n")
        task_md.advance(1)


def build_coverage_matrix(*, input_dir: str, out_dir: str) -> None:
    with progress.phase("coverage: init"):
        input_root = Path(input_dir)
        if not input_root.is_dir():
            raise ValueError("--input must be an unpacked export directory")
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

    with progress.phase("coverage: resolve layout"):
        layout = resolve_export_layout(input_root)
        export_root = input_root if layout.export_root_rel == "." else (input_root / layout.export_root_rel)
        clinical_dir = export_root / layout.clinical_dir_rel if isinstance(layout.clinical_dir_rel, str) else export_root / "clinical-records"
        export_cda = export_root / layout.export_cda_rel if isinstance(layout.export_cda_rel, str) else export_root / "export_cda.xml"

    with progress.phase("coverage: scan clinical JSON"):
        fhir_counts, fhir_meta, _schema, _sensitive = _count_clinical_resource_types(clinical_dir, sample_json=0)
    with progress.phase("coverage: scan CDA sections"):
        cda_sections = _count_cda_sections(export_cda) if export_cda.exists() else []

    mapped = set(FHIR_CANONICAL_MAPPING_RESOURCE_TYPES)
    rows_unsorted = []
    for resource_type, count in fhir_counts:
        rows_unsorted.append(
            {
                "resourceType": resource_type,
                "count": int(count),
                "has_canonical_mapping": resource_type in mapped,
            }
        )
    rows = sorted(rows_unsorted, key=lambda row: (row["has_canonical_mapping"], -int(row["count"]), row["resourceType"]))

    top_unmapped = [row for row in rows if not row["has_canonical_mapping"]]
    coverage = {
        "schema_version": 1,
        "summary": {
            "clinical_json_total_files": fhir_meta["total_files"],
            "clinical_json_sampled_files": fhir_meta["sampled_files"],
            "mapped_resource_type_count": sum(1 for row in rows if row["has_canonical_mapping"]),
            "unmapped_resource_type_count": sum(1 for row in rows if not row["has_canonical_mapping"]),
        },
        "resource_types": rows,
        "cda_sections": cda_sections,
        "top_unmapped_resource_types": top_unmapped[:10],
        "canonical_mapping_resource_types": sorted(mapped),
        "notes": {
            "privacy": "Share-safe: counts and structured resource/section labels only.",
            "determinism": "Stable ordering and formatting for identical export fixtures.",
        },
    }

    with progress.phase("coverage: write artifacts"):
        task = progress.task("coverage: write artifacts", total=2, unit="files")
        _write_json(out / "coverage_matrix.json", coverage)
        task.advance(1)
        lines = [
            "# Clinical Coverage Matrix",
            "",
            "## Summary",
            f"- clinical_json_total_files: {fhir_meta['total_files']}",
            f"- mapped_resource_type_count: {coverage['summary']['mapped_resource_type_count']}",
            f"- unmapped_resource_type_count: {coverage['summary']['unmapped_resource_type_count']}",
            "",
            "## Resource Types",
        ]
        if rows:
            for row in rows:
                lines.append(
                    f"- {row['resourceType']}: count={row['count']} mapped={'yes' if row['has_canonical_mapping'] else 'no'}"
                )
        else:
            lines.append("- none")
        lines.append("")
        lines.append("## Top Unmapped Resources")
        if top_unmapped:
            for row in top_unmapped[:10]:
                lines.append(f"- {row['resourceType']}: {row['count']}")
        else:
            lines.append("- none")
        lines.append("")
        lines.append("## CDA Sections")
        if cda_sections:
            for row in cda_sections:
                label_parts = [row.get("section_title"), row.get("section_display"), row.get("section_code")]
                label = " | ".join(part for part in label_parts if isinstance(part, str) and part)
                lines.append(f"- {label}: {row['count']}")
        else:
            lines.append("- none")
        lines.append("")
        lines.append("## Privacy")
        lines.append("- Share-safe: only aggregate counts and structured labels are emitted.")
        _write_text_atomic(out / "coverage_matrix.md", "\n".join(lines) + "\n")
        task.advance(1)
