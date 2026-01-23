from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from healthdelta.progress import progress


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


_WS_RE = re.compile(r"\s+")


def _collapse_ws(s: str) -> str:
    return _WS_RE.sub(" ", s.strip())


def _localname(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


@dataclass(frozen=True)
class PersonPseudonym:
    canonical_person_id: str
    first_norm: str
    last_norm: str
    label: str  # "Patient N"

    @property
    def patterns(self) -> list[re.Pattern[str]]:
        first = re.escape(self.first_norm)
        last = re.escape(self.last_norm)
        return [
            re.compile(rf"\b{first}\s+{last}\b", re.IGNORECASE),
            re.compile(rf"\b{last}\s*,\s*{first}\b", re.IGNORECASE),
        ]


def _load_people(identity_dir: Path) -> list[PersonPseudonym]:
    people_path = identity_dir / "people.json"
    obj = _read_json(people_path)
    people = obj.get("people") if isinstance(obj, dict) else None
    if not isinstance(people, list):
        raise ValueError(f"Invalid people.json format: {people_path}")

    parsed = []
    for p in people:
        if not isinstance(p, dict):
            continue
        person_key = p.get("person_key")
        first_norm = p.get("first_norm")
        last_norm = p.get("last_norm")
        if not (isinstance(person_key, str) and isinstance(first_norm, str) and isinstance(last_norm, str)):
            continue
        parsed.append((last_norm, first_norm, person_key, first_norm, last_norm))

    parsed.sort()
    out: list[PersonPseudonym] = []
    for i, (_, __, person_key, first_norm, last_norm) in enumerate(parsed, start=1):
        out.append(PersonPseudonym(canonical_person_id=person_key, first_norm=first_norm, last_norm=last_norm, label=f"Patient {i}"))
    return out


def _apply_name_replacements(text: str, people: list[PersonPseudonym]) -> str:
    out = text
    for person in people:
        for pat in person.patterns:
            out = pat.sub(person.label, out)
    return out


def _deid_cda_xml(xml_text: str, people: list[PersonPseudonym]) -> str:
    root = ET.fromstring(xml_text)
    for patient_role in root.iter():
        if _localname(patient_role.tag) != "patientRole":
            continue

        patient = None
        for child in list(patient_role):
            if _localname(child.tag) == "patient":
                patient = child
                break
        if patient is None:
            continue

        for name_el in list(patient):
            if _localname(name_el.tag) == "name":
                name_el.clear()
                name_el.text = "Patient 1"

        for bt in patient.iter():
            if _localname(bt.tag) == "birthTime":
                bt.attrib["value"] = "19000101"

    rendered = ET.tostring(root, encoding="unicode")
    rendered = _apply_name_replacements(rendered, people)
    return rendered


def _deid_export_xml(xml_text: str, people: list[PersonPseudonym]) -> str:
    return _apply_name_replacements(xml_text, people)


def _deep_replace_strings(obj: Any, *, people: list[PersonPseudonym]) -> Any:
    if isinstance(obj, str):
        return _apply_name_replacements(obj, people)
    if isinstance(obj, list):
        return [_deep_replace_strings(v, people=people) for v in obj]
    if isinstance(obj, dict):
        return {k: _deep_replace_strings(v, people=people) for k, v in obj.items()}
    return obj


def _deid_fhir_json(obj: Any, people: list[PersonPseudonym]) -> Any:
    obj = _deep_replace_strings(obj, people=people)
    if isinstance(obj, dict) and obj.get("resourceType") == "Patient":
        names = obj.get("name")
        if isinstance(names, list):
            for n in names:
                if not isinstance(n, dict):
                    continue
                # Minimal: rewrite common display forms.
                n["text"] = people[0].label if people else "Patient 1"
                n["given"] = ["Patient"]
                n["family"] = people[0].label.split(" ", 1)[1] if people else "1"
        if "birthDate" in obj:
            obj["birthDate"] = "1900-01-01"
    return obj


def deidentify_run(*, staging_run_dir: str, identity_dir: str, out_dir: str) -> None:
    with progress.phase("deid: init"):
        run_dir = Path(staging_run_dir)
        out_root = Path(out_dir)
        identity = Path(identity_dir)

    layout_path = run_dir / "layout.json"
    if not layout_path.exists():
        raise FileNotFoundError("Missing layout.json in staging run dir")

    with progress.phase("deid: load layout"):
        layout = _read_json(layout_path)
        run_id = layout.get("run_id") if isinstance(layout.get("run_id"), str) else run_dir.name

    with progress.phase("deid: load people"):
        people = _load_people(identity)
        mapping = {p.canonical_person_id: p.label for p in people}
        _write_json(out_root / "mapping.json", mapping)
        mapping_path = out_root / "mapping.json"

    export_xml_rel = layout.get("export_xml")
    clinical_rels = layout.get("clinical_json")
    if export_xml_rel is not None and not isinstance(export_xml_rel, str):
        raise ValueError("layout.json export_xml must be a string")
    if clinical_rels is None:
        clinical_rels = []
    if not isinstance(clinical_rels, list):
        raise ValueError("layout.json clinical_json must be a list")

    # Optional CDA file (not guaranteed to be staged by ingest yet)
    export_cda_rel = "source/unpacked/export_cda.xml"
    export_cda_path = run_dir / export_cda_rel
    has_cda = export_cda_path.exists()

    out_root.mkdir(parents=True, exist_ok=True)

    started_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    output_files: list[Path] = []
    if mapping_path.exists():
        output_files.append(mapping_path)

    if isinstance(export_xml_rel, str):
        with progress.phase("deid: export.xml"):
            src = run_dir / export_xml_rel
            if src.exists():
                dst = out_root / export_xml_rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                text = src.read_text(encoding="utf-8", errors="replace")
                dst.write_text(_deid_export_xml(text, people), encoding="utf-8")
                output_files.append(dst)

    if has_cda:
        with progress.phase("deid: export_cda.xml"):
            dst = out_root / export_cda_rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            text = export_cda_path.read_text(encoding="utf-8", errors="replace")
            dst.write_text(_deid_cda_xml(text, people), encoding="utf-8")
            output_files.append(dst)

    out_clinical_rels: list[str] = []
    with progress.phase("deid: clinical files"):
        task = progress.task("deid: clinical files", total=len(clinical_rels), unit="files")
        for rel in clinical_rels:
            if not isinstance(rel, str):
                task.advance(1)
                continue
            src = run_dir / rel
            if not src.exists():
                task.advance(1)
                continue
            dst = out_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                obj = _read_json(src)
                obj = _deid_fhir_json(obj, people)
                dst.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            except json.JSONDecodeError:
                text = src.read_text(encoding="utf-8", errors="replace")
                dst.write_text(_apply_name_replacements(text, people), encoding="utf-8")
            output_files.append(dst)
            out_clinical_rels.append(rel)
            task.advance(1)

    with progress.phase("deid: write manifest"):
        task = progress.task("deid: hash outputs", total=len(output_files), unit="files")
        files_out: list[dict[str, object]] = []
        for p in output_files:
            files_out.append(
                {
                    "path": p.relative_to(out_root).as_posix(),
                    "size_bytes": p.stat().st_size,
                    "sha256": _sha256_file(p),
                }
            )
            task.advance(1)

        # Copy through any staged paths that aren't explicitly de-id'd? MVP: only the listed assets.
        manifest = {
            "run_id": run_id,
            "source": {
                "staging_run_dir_redacted": True,
                "run_id": run_id,
                "identity_dir_redacted": True,
                "identity_people_sha256": _sha256_file(identity / "people.json"),
            },
            "files": sorted(files_out, key=lambda x: str(x.get("path") or "")),
            "timestamps": {
                "started_at": started_at,
                "finished_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            },
            "determinism": {
                "stable_fields": ["run_id", "source.identity_people_sha256", "files[*].sha256", "files[*].size_bytes"],
                "time_fields": ["timestamps.*"],
            },
            "notes": {
                "covered": [
                    "name replacement for known people (First Last, Last, First)",
                    "CDA patientRole/patient/name overwrite",
                    "CDA birthTime value redaction",
                    "FHIR Patient.name minimal rewrite",
                ],
                "not_covered_yet": [
                    "full FHIR-wide PII scrubbing",
                    "identifier redaction in every field",
                    "free-text PII outside targeted replacements",
                ],
            },
        }

    out_layout = {
        "run_id": run_id,
        "export_xml": export_xml_rel if isinstance(export_xml_rel, str) else None,
        "export_cda_xml": export_cda_rel if has_cda else None,
        "clinical_json": out_clinical_rels,
    }

    with progress.phase("deid: write outputs"):
        task = progress.task("deid: write outputs", total=2, unit="files")
        _write_json(out_root / "manifest.json", manifest)
        task.advance(1)
        _write_json(out_root / "layout.json", out_layout)
        task.advance(1)
