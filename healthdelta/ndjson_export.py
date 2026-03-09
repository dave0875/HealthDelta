from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET

from healthdelta.progress import progress


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _source_system_tag(raw: str) -> str:
    return "ss_" + _sha256_bytes(raw.encode("utf-8"))[:12]


def _write_ndjson(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent)) as tf:
        tmp = Path(tf.name)
        task = progress.task(f"Write {path.name}", total=len(rows), unit="rows")
        batch = 0
        for row in rows:
            tf.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            batch += 1
            if batch >= 1000:
                task.advance(batch)
                batch = 0
        if batch:
            task.advance(batch)
    tmp.replace(path)


def _localname(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _normalize_time(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    if not s:
        return None

    # HealthKit export.xml uses: "YYYY-MM-DD HH:MM:SS -0500"
    try:
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z").astimezone(timezone.utc).replace(microsecond=0)
        return dt.isoformat().replace("+00:00", "Z")
    except ValueError:
        pass

    # CDA effectiveTime @value often uses: "YYYYMMDDHHMMSS"
    if len(s) == 14 and s.isdigit():
        try:
            dt = datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")
        except ValueError:
            pass

    # FHIR often uses ISO-8601; accept "Z" suffix.
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc).replace(microsecond=0)
        return dt.isoformat().replace("+00:00", "Z")
    except ValueError:
        return s


def _safe_relpath(path: str) -> str:
    # Inputs are expected to be relative paths from layout.json; ensure we never emit absolute paths.
    p = Path(path)
    if p.is_absolute():
        return p.name
    return p.as_posix()


@dataclass(frozen=True)
class ExportContext:
    run_id: str
    root_dir: Path  # staging run dir for local, deid run dir for share
    export_xml_rel: str | None
    export_cda_rel: str | None
    clinical_json_rels: list[str]
    identity_dir: Path | None
    person_default: str | None
    patient_id_map: dict[tuple[str, str], str]  # (system,value)->canonical_person_id


def _load_identity(identity_dir: Path) -> tuple[str | None, dict[tuple[str, str], str]]:
    people_path = identity_dir / "people.json"
    aliases_path = identity_dir / "aliases.json"

    default_person_id: str | None = None
    if people_path.exists():
        obj = _read_json(people_path)
        people = obj.get("people") if isinstance(obj, dict) else None
        if isinstance(people, list) and len(people) == 1 and isinstance(people[0], dict) and isinstance(people[0].get("person_key"), str):
            default_person_id = people[0]["person_key"]

    mapping: dict[tuple[str, str], str] = {}
    if aliases_path.exists():
        obj = _read_json(aliases_path)
        aliases = obj.get("aliases") if isinstance(obj, dict) else None
        if isinstance(aliases, list):
            for a in aliases:
                if not isinstance(a, dict):
                    continue
                person_key = a.get("person_key")
                src = a.get("source")
                if not (isinstance(person_key, str) and isinstance(src, dict)):
                    continue
                external = src.get("external_ids")
                if isinstance(external, list):
                    for ext in external:
                        if not isinstance(ext, dict):
                            continue
                        system = ext.get("system")
                        value = ext.get("value")
                        if isinstance(system, str) and isinstance(value, str) and system.strip() and value.strip():
                            mapping[(system, value)] = person_key
    return default_person_id, mapping


def _resolve_context(*, input_dir: Path, mode: str) -> ExportContext:
    if mode not in {"local", "share"}:
        raise ValueError("--mode must be one of: local, share")

    run_root = input_dir
    if not (run_root / "layout.json").exists():
        raise FileNotFoundError(f"Missing layout.json: {run_root}")

    layout = _read_json(run_root / "layout.json")
    run_id = layout.get("run_id") if isinstance(layout, dict) and isinstance(layout.get("run_id"), str) else run_root.name

    export_xml_rel = layout.get("export_xml") if isinstance(layout.get("export_xml"), str) else None
    clinical_json = layout.get("clinical_json")
    clinical_rels = [r for r in clinical_json if isinstance(r, str)] if isinstance(clinical_json, list) else []

    export_cda_rel: str | None = None
    if isinstance(layout, dict) and isinstance(layout.get("export_cda_xml"), str):
        export_cda_rel = layout["export_cda_xml"]
    else:
        # Pipeline stages CDA here even if staging layout.json doesn't include it.
        candidate = "source/unpacked/export_cda.xml"
        if (run_root / candidate).exists():
            export_cda_rel = candidate

    base_dir: Path | None = None
    # Supported layouts:
    # - Legacy: <base>/(staging|deid)/<run_id>
    # - Operator (Issue #12): <base>/<run_id>/(staging|deid)
    if run_root.name in {"staging", "deid"}:
        base_dir = run_root.parent
    elif run_root.parent.name in {"staging", "deid"}:
        base_dir = run_root.parent.parent

    identity_dir: Path | None = None
    default_person_id: str | None = None
    patient_id_map: dict[tuple[str, str], str] = {}

    if base_dir is not None:
        candidates = [
            base_dir / "identity",
            base_dir / "state" / "identity",
            base_dir.parent / "state" / "identity",
        ]
        candidate_identity = next((p for p in candidates if p.exists()), None)
        if candidate_identity is not None:
            identity_dir = candidate_identity
            default_person_id, patient_id_map = _load_identity(candidate_identity)

        if mode == "share" and default_person_id is None and (run_root / "mapping.json").exists():
            mapping_obj = _read_json(run_root / "mapping.json")
            if isinstance(mapping_obj, dict) and len(mapping_obj) == 1:
                only_key = next(iter(mapping_obj.keys()))
                if isinstance(only_key, str):
                    default_person_id = only_key

    return ExportContext(
        run_id=run_id,
        root_dir=run_root,
        export_xml_rel=export_xml_rel,
        export_cda_rel=export_cda_rel,
        clinical_json_rels=sorted(clinical_rels),
        identity_dir=identity_dir,
        person_default=default_person_id,
        patient_id_map=patient_id_map,
    )


def _canonical_person_id(ctx: ExportContext, *, system: str | None = None, value: str | None = None) -> str:
    if system and value:
        mapped = ctx.patient_id_map.get((system, value))
        if isinstance(mapped, str):
            return mapped
    if ctx.person_default is not None:
        return ctx.person_default
    return "unresolved"


def _extract_fhir_subject_patient_id(resource: dict) -> str | None:
    subj = resource.get("subject")
    if isinstance(subj, dict):
        ref = subj.get("reference")
        if isinstance(ref, str) and ref.startswith("Patient/"):
            return ref.split("/", 1)[1]
    patient = resource.get("patient")
    if isinstance(patient, dict):
        ref = patient.get("reference")
        if isinstance(ref, str) and ref.startswith("Patient/"):
            return ref.split("/", 1)[1]
    return None


def _extract_identifier_pairs(value: Any) -> list[tuple[str, str]]:
    items = value if isinstance(value, list) else [value]
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        system = item.get("system")
        ident_value = item.get("value")
        if not (isinstance(system, str) and isinstance(ident_value, str)):
            continue
        system = system.strip()
        ident_value = ident_value.strip()
        if not system or not ident_value:
            continue
        pair = (system, ident_value)
        if pair not in seen:
            seen.add(pair)
            pairs.append(pair)
    return pairs


def _extract_fhir_reference_identifier_pairs(resource: dict) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for key in ("subject", "patient"):
        ref = resource.get(key)
        if not isinstance(ref, dict):
            continue
        ident = ref.get("identifier")
        pairs.extend(_extract_identifier_pairs(ident))
    return pairs


def _resolve_fhir_person_id(ctx: ExportContext, resource: dict) -> str:
    candidates: set[str] = set()
    subject_patient_id = _extract_fhir_subject_patient_id(resource)
    if subject_patient_id:
        mapped = ctx.patient_id_map.get(("fhir:id", subject_patient_id))
        if isinstance(mapped, str):
            candidates.add(mapped)

    for system, value in _extract_fhir_reference_identifier_pairs(resource):
        mapped = ctx.patient_id_map.get((system, value))
        if isinstance(mapped, str):
            candidates.add(mapped)

    if len(candidates) == 1:
        return next(iter(candidates))
    if len(candidates) > 1:
        return "unresolved"

    if subject_patient_id:
        return _canonical_person_id(ctx, system="fhir:id", value=subject_patient_id)
    return _canonical_person_id(ctx)


def _derive_fhir_source_system(resource: dict) -> str:
    meta = resource.get("meta")
    if isinstance(meta, dict):
        src = meta.get("source")
        if isinstance(src, str) and src.strip():
            return _source_system_tag(f"meta.source:{src.strip()}")
    pairs = _extract_fhir_reference_identifier_pairs(resource)
    for system, _ in pairs:
        if isinstance(system, str) and system.strip():
            return _source_system_tag(f"identifier.system:{system.strip()}")
    return _source_system_tag("fhir:default")


def _extract_fhir_reference_id(ref: str, resource_type: str) -> str | None:
    if not isinstance(ref, str) or not ref.strip():
        return None
    ref = ref.strip()
    prefix = f"{resource_type}/"
    if ref.startswith(prefix):
        return ref.split("/", 1)[1]
    token = f"/{resource_type}/"
    if token in ref:
        return ref.rsplit("/", 1)[1]
    return None


def _first_fhir_coding_value(codable: object, field: str) -> str | None:
    if not isinstance(codable, dict):
        return None
    coding = codable.get("coding")
    if not isinstance(coding, list):
        return None
    for item in coding:
        if not isinstance(item, dict):
            continue
        value = item.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _walk_source_fhir_files(ctx: ExportContext) -> Iterable[tuple[str, dict]]:
    for rel in ctx.clinical_json_rels:
        p = ctx.root_dir / rel
        if not p.exists():
            continue
        try:
            obj = _read_json(p)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            yield rel, obj


def _export_healthkit_observations(ctx: ExportContext) -> list[dict]:
    if not ctx.export_xml_rel:
        return []
    path = ctx.root_dir / ctx.export_xml_rel
    if not path.exists():
        return []

    observations: list[dict] = []
    task = progress.task("Parse export.xml records", total=None, unit="records")
    batch = 0
    for _, el in ET.iterparse(path, events=("end",)):
        if _localname(el.tag) != "Record":
            continue
        hk_type = el.attrib.get("type")
        if not hk_type:
            el.clear()
            continue
        start = _normalize_time(el.attrib.get("startDate"))
        end = _normalize_time(el.attrib.get("endDate"))
        value = el.attrib.get("value")
        unit = el.attrib.get("unit")
        event_time = start or end

        minimal = {
            "schema_version": 2,
            "canonical_person_id": _canonical_person_id(ctx),
            "source": "healthkit",
            "source_system": _source_system_tag("healthkit:export.xml"),
            "source_file": _safe_relpath(ctx.export_xml_rel),
            "event_time": event_time,
            "run_id": ctx.run_id,
            "hk_type": hk_type,
            "value": value,
            "unit": unit,
        }
        minimal["event_key"] = _sha256_bytes(json.dumps(minimal, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        minimal["record_key"] = minimal["event_key"]
        observations.append(minimal)
        el.clear()
        batch += 1
        if batch >= 1000:
            task.advance(batch)
            batch = 0

    if batch:
        task.advance(batch)
    return observations


def _fhir_event_time(resource: dict) -> str | None:
    rt = resource.get("resourceType")
    if rt == "Observation":
        t = resource.get("effectiveDateTime")
        if isinstance(t, str):
            return _normalize_time(t)
        period = resource.get("effectivePeriod")
        if isinstance(period, dict) and isinstance(period.get("start"), str):
            return _normalize_time(period["start"])
        issued = resource.get("issued")
        if isinstance(issued, str):
            return _normalize_time(issued)
    if rt == "DocumentReference":
        t = resource.get("date")
        if isinstance(t, str):
            return _normalize_time(t)
        indexed = resource.get("indexed")
        if isinstance(indexed, str):
            return _normalize_time(indexed)
    if rt == "MedicationRequest":
        t = resource.get("authoredOn")
        if isinstance(t, str):
            return _normalize_time(t)
    if rt == "MedicationStatement":
        t = resource.get("effectiveDateTime")
        if isinstance(t, str):
            return _normalize_time(t)
        period = resource.get("effectivePeriod")
        if isinstance(period, dict):
            start = period.get("start")
            if isinstance(start, str):
                return _normalize_time(start)
            end = period.get("end")
            if isinstance(end, str):
                return _normalize_time(end)
    if rt == "MedicationDispense":
        t = resource.get("whenHandedOver")
        if isinstance(t, str):
            return _normalize_time(t)
        t = resource.get("whenPrepared")
        if isinstance(t, str):
            return _normalize_time(t)
    if rt == "Condition":
        t = resource.get("recordedDate")
        if isinstance(t, str):
            return _normalize_time(t)
        onset = resource.get("onsetDateTime")
        if isinstance(onset, str):
            return _normalize_time(onset)
    if rt == "AllergyIntolerance":
        onset = resource.get("onsetDateTime")
        if isinstance(onset, str):
            return _normalize_time(onset)
        t = resource.get("recordedDate")
        if isinstance(t, str):
            return _normalize_time(t)
    if rt == "Immunization":
        t = resource.get("occurrenceDateTime")
        if isinstance(t, str):
            return _normalize_time(t)
    if rt == "Encounter":
        period = resource.get("period")
        if isinstance(period, dict):
            start = period.get("start")
            if isinstance(start, str):
                return _normalize_time(start)
            end = period.get("end")
            if isinstance(end, str):
                return _normalize_time(end)
        return None
    if rt == "Procedure":
        t = resource.get("performedDateTime")
        if isinstance(t, str):
            return _normalize_time(t)
        period = resource.get("performedPeriod")
        if isinstance(period, dict):
            start = period.get("start")
            if isinstance(start, str):
                return _normalize_time(start)
            end = period.get("end")
            if isinstance(end, str):
                return _normalize_time(end)
    if rt == "DiagnosticReport":
        t = resource.get("effectiveDateTime")
        if isinstance(t, str):
            return _normalize_time(t)
        period = resource.get("effectivePeriod")
        if isinstance(period, dict):
            start = period.get("start")
            if isinstance(start, str):
                return _normalize_time(start)
            end = period.get("end")
            if isinstance(end, str):
                return _normalize_time(end)
        issued = resource.get("issued")
        if isinstance(issued, str):
            return _normalize_time(issued)
    return None


def _export_fhir_streams(
    ctx: ExportContext,
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict], list[dict], list[dict]]:
    observations: list[dict] = []
    documents: list[dict] = []
    meds: list[dict] = []
    conds: list[dict] = []
    encounters: list[dict] = []
    procedures: list[dict] = []
    diagnostic_reports: list[dict] = []
    observation_keys: dict[str, str] = {}
    pending_report_links: list[tuple[dict, list[str]]] = []
    condition_warning_counts: dict[str, int] = {}
    medication_warning_counts: dict[str, int] = {}
    allergy_warning_counts: dict[str, int] = {}
    immunization_warning_counts: dict[str, int] = {}
    procedure_warning_counts: dict[str, int] = {}

    task_files = progress.task("Parse FHIR JSON files", total=len(ctx.clinical_json_rels), unit="files")
    for rel in ctx.clinical_json_rels:
        p = ctx.root_dir / rel
        if not p.exists():
            task_files.advance(1)
            continue
        try:
            res = _read_json(p)
        except json.JSONDecodeError:
            task_files.advance(1)
            continue
        if not isinstance(res, dict):
            task_files.advance(1)
            continue

        rt = res.get("resourceType")
        if not isinstance(rt, str):
            task_files.advance(1)
            continue

        # Patient resources are used only for identity mapping; do not emit them.
        if rt == "Patient":
            task_files.advance(1)
            continue

        rid = res.get("id") if isinstance(res.get("id"), str) else None
        person = _resolve_fhir_person_id(ctx, res)
        event_time = _fhir_event_time(res)

        base = {
            "schema_version": 2,
            "canonical_person_id": person,
            "source": "fhir",
            "source_system": _derive_fhir_source_system(res),
            "source_file": _safe_relpath(rel),
            "event_time": event_time,
            "run_id": ctx.run_id,
            "resource_type": rt,
            "source_id": f"{rt}/{rid}" if rid else None,
        }

        if rt == "Observation":
            code = res.get("code")
            if isinstance(code, dict):
                coding = code.get("coding")
                if isinstance(coding, list):
                    codings: list[dict[str, str]] = []
                    for c in coding:
                        if not isinstance(c, dict):
                            continue
                        system = c.get("system")
                        code_val = c.get("code")
                        if isinstance(system, str) and isinstance(code_val, str) and system.strip() and code_val.strip():
                            codings.append({"system": system, "code": code_val})
                    if codings:
                        base["code_coding"] = sorted(codings, key=lambda x: (x["system"], x["code"]))
            val = res.get("valueQuantity")
            if isinstance(val, dict):
                if "value" in val:
                    base["value"] = val["value"]
                if isinstance(val.get("unit"), str):
                    base["unit"] = val["unit"]
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            observations.append(base)
            if rid and isinstance(base.get("record_key"), str):
                observation_keys[rid] = base["record_key"]
                observation_keys[f"Observation/{rid}"] = base["record_key"]
        elif rt == "DocumentReference":
            t = res.get("type")
            if isinstance(t, dict):
                coding = t.get("coding")
                if isinstance(coding, list):
                    codings = []
                    for c in coding:
                        if not isinstance(c, dict):
                            continue
                        system = c.get("system")
                        code_val = c.get("code")
                        if isinstance(system, str) and isinstance(code_val, str) and system.strip() and code_val.strip():
                            codings.append({"system": system, "code": code_val})
                    if codings:
                        base["type_coding"] = sorted(codings, key=lambda x: (x["system"], x["code"]))
            status = res.get("status")
            if isinstance(status, str):
                base["status"] = status
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            documents.append(base)
        elif rt in {"MedicationRequest", "MedicationStatement", "MedicationDispense"}:
            status = res.get("status")
            if isinstance(status, str):
                base["status"] = status
            med = res.get("medicationCodeableConcept")
            if isinstance(med, dict):
                base["code_system"] = _first_fhir_coding_value(med, "system")
                base["code"] = _first_fhir_coding_value(med, "code")
                display = _first_fhir_coding_value(med, "display")
                if display is None:
                    text = med.get("text")
                    if isinstance(text, str) and text.strip():
                        display = text.strip()
                base["display"] = display
            if base.get("code") is None:
                medication_warning_counts["code"] = int(medication_warning_counts.get("code", 0)) + 1
            if base.get("status") is None:
                medication_warning_counts["status"] = int(medication_warning_counts.get("status", 0)) + 1
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            meds.append(base)
        elif rt in {"Condition", "AllergyIntolerance"}:
            code = res.get("code")
            if isinstance(code, dict):
                coding = code.get("coding")
                if isinstance(coding, list):
                    codings = []
                    for c in coding:
                        if not isinstance(c, dict):
                            continue
                        system = c.get("system")
                        code_val = c.get("code")
                        if isinstance(system, str) and isinstance(code_val, str) and system.strip() and code_val.strip():
                            codings.append({"system": system, "code": code_val})
                    if codings:
                        base["code_coding"] = sorted(codings, key=lambda x: (x["system"], x["code"]))
            if rt == "Condition":
                base["code_system"] = _first_fhir_coding_value(res.get("code"), "system")
                base["code"] = _first_fhir_coding_value(res.get("code"), "code")
                display = _first_fhir_coding_value(res.get("code"), "display")
                if display is None and isinstance(res.get("code"), dict):
                    text = res["code"].get("text")
                    if isinstance(text, str) and text.strip():
                        display = text.strip()
                base["display"] = display
                base["clinical_status"] = _first_fhir_coding_value(res.get("clinicalStatus"), "code")
                base["verification_status"] = _first_fhir_coding_value(res.get("verificationStatus"), "code")
                onset = res.get("onsetDateTime")
                base["onset_time"] = _normalize_time(onset) if isinstance(onset, str) else None
                for key in ["code", "clinical_status", "verification_status"]:
                    if base.get(key) is None:
                        condition_warning_counts[key] = int(condition_warning_counts.get(key, 0)) + 1
            elif rt == "AllergyIntolerance":
                base["code_system"] = _first_fhir_coding_value(res.get("code"), "system")
                base["code"] = _first_fhir_coding_value(res.get("code"), "code")
                display = _first_fhir_coding_value(res.get("code"), "display")
                if display is None and isinstance(res.get("code"), dict):
                    text = res["code"].get("text")
                    if isinstance(text, str) and text.strip():
                        display = text.strip()
                base["display"] = display
                base["status"] = _first_fhir_coding_value(res.get("clinicalStatus"), "code")
                if base.get("code") is None:
                    allergy_warning_counts["code"] = int(allergy_warning_counts.get("code", 0)) + 1
                if base.get("status") is None:
                    allergy_warning_counts["status"] = int(allergy_warning_counts.get("status", 0)) + 1
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            conds.append(base)
        elif rt == "Immunization":
            status = res.get("status")
            if isinstance(status, str):
                base["status"] = status
            vaccine_code = res.get("vaccineCode")
            if isinstance(vaccine_code, dict):
                base["code_system"] = _first_fhir_coding_value(vaccine_code, "system")
                base["code"] = _first_fhir_coding_value(vaccine_code, "code")
                display = _first_fhir_coding_value(vaccine_code, "display")
                if display is None:
                    text = vaccine_code.get("text")
                    if isinstance(text, str) and text.strip():
                        display = text.strip()
                base["display"] = display
                coding = vaccine_code.get("coding")
                if isinstance(coding, list):
                    codings = []
                    for c in coding:
                        if not isinstance(c, dict):
                            continue
                        system = c.get("system")
                        code_val = c.get("code")
                        if isinstance(system, str) and isinstance(code_val, str) and system.strip() and code_val.strip():
                            codings.append({"system": system, "code": code_val})
                    if codings:
                        base["code_coding"] = sorted(codings, key=lambda x: (x["system"], x["code"]))
            if base.get("code") is None:
                immunization_warning_counts["code"] = int(immunization_warning_counts.get("code", 0)) + 1
            if base.get("status") is None:
                immunization_warning_counts["status"] = int(immunization_warning_counts.get("status", 0)) + 1
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            observations.append(base)
        elif rt == "Encounter":
            if rid:
                base["record_id"] = rid
                base["encounter_id"] = rid
            base["record_type"] = "Encounter"
            status = res.get("status")
            if isinstance(status, str):
                base["status"] = status
            subject = res.get("subject")
            if isinstance(subject, dict):
                subject_reference = subject.get("reference")
                if isinstance(subject_reference, str) and subject_reference.strip():
                    base["subject_reference"] = subject_reference.strip()
            klass = res.get("class")
            if isinstance(klass, dict):
                code = klass.get("code")
                system = klass.get("system")
                if isinstance(code, str) and code.strip():
                    base["class_code"] = code
                if isinstance(system, str) and system.strip():
                    base["class_system"] = system
            period = res.get("period")
            if isinstance(period, dict):
                start = period.get("start")
                end = period.get("end")
                base["period_start"] = _normalize_time(start) if isinstance(start, str) else None
                base["period_end"] = _normalize_time(end) if isinstance(end, str) else None
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            encounters.append(base)
        elif rt == "Procedure":
            status = res.get("status")
            if isinstance(status, str):
                base["status"] = status
            code = res.get("code")
            if isinstance(code, dict):
                base["code_system"] = _first_fhir_coding_value(code, "system")
                base["code"] = _first_fhir_coding_value(code, "code")
                display = _first_fhir_coding_value(code, "display")
                if display is None:
                    text = code.get("text")
                    if isinstance(text, str) and text.strip():
                        display = text.strip()
                base["display"] = display
                coding = code.get("coding")
                if isinstance(coding, list):
                    codings = []
                    for c in coding:
                        if not isinstance(c, dict):
                            continue
                        system = c.get("system")
                        code_val = c.get("code")
                        if isinstance(system, str) and isinstance(code_val, str) and system.strip() and code_val.strip():
                            codings.append({"system": system, "code": code_val})
                    if codings:
                        base["code_coding"] = sorted(codings, key=lambda x: (x["system"], x["code"]))
            if base.get("code") is None:
                procedure_warning_counts["code"] = int(procedure_warning_counts.get("code", 0)) + 1
            if base.get("status") is None:
                procedure_warning_counts["status"] = int(procedure_warning_counts.get("status", 0)) + 1
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            procedures.append(base)
        elif rt == "DiagnosticReport":
            status = res.get("status")
            if isinstance(status, str):
                base["status"] = status
            code = res.get("code")
            if isinstance(code, dict):
                coding = code.get("coding")
                if isinstance(coding, list):
                    codings = []
                    for c in coding:
                        if not isinstance(c, dict):
                            continue
                        system = c.get("system")
                        code_val = c.get("code")
                        if isinstance(system, str) and isinstance(code_val, str) and system.strip() and code_val.strip():
                            codings.append({"system": system, "code": code_val})
                    if codings:
                        base["code_coding"] = sorted(codings, key=lambda x: (x["system"], x["code"]))
            result_refs: list[str] = []
            result = res.get("result")
            if isinstance(result, list):
                for item in result:
                    if not isinstance(item, dict):
                        continue
                    ref = item.get("reference")
                    if not isinstance(ref, str):
                        continue
                    obs_id = _extract_fhir_reference_id(ref, "Observation")
                    if obs_id:
                        result_refs.append(obs_id)
            if result_refs:
                resolved = sorted(
                    {
                        observation_keys.get(r) or observation_keys.get(f"Observation/{r}")
                        for r in result_refs
                        if observation_keys.get(r) or observation_keys.get(f"Observation/{r}")
                    }
                )
                if resolved:
                    base["result_observation_record_keys"] = resolved
                else:
                    pending_report_links.append((base, result_refs))
            diagnostic_reports.append(base)
        task_files.advance(1)

    if pending_report_links:
        for report, refs in pending_report_links:
            resolved = sorted(
                {
                    observation_keys.get(r) or observation_keys.get(f"Observation/{r}")
                    for r in refs
                    if observation_keys.get(r) or observation_keys.get(f"Observation/{r}")
                }
            )
            if resolved:
                report["result_observation_record_keys"] = resolved

    for report in diagnostic_reports:
        report["event_key"] = _sha256_bytes(
            json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        report["record_key"] = report["event_key"]

    if condition_warning_counts:
        for key in sorted(condition_warning_counts):
            sys.stderr.write(f"warnings.condition_missing.{key}={condition_warning_counts[key]}\n")
    if medication_warning_counts:
        for key in sorted(medication_warning_counts):
            sys.stderr.write(f"warnings.medication_missing.{key}={medication_warning_counts[key]}\n")
    if allergy_warning_counts:
        for key in sorted(allergy_warning_counts):
            sys.stderr.write(f"warnings.allergy_missing.{key}={allergy_warning_counts[key]}\n")
    if immunization_warning_counts:
        for key in sorted(immunization_warning_counts):
            sys.stderr.write(f"warnings.immunization_missing.{key}={immunization_warning_counts[key]}\n")
    if procedure_warning_counts:
        for key in sorted(procedure_warning_counts):
            sys.stderr.write(f"warnings.procedure_missing.{key}={procedure_warning_counts[key]}\n")

    return observations, documents, meds, conds, encounters, procedures, diagnostic_reports


def _xml_child_text(el: ET.Element, name: str) -> str | None:
    for child in list(el):
        if _localname(child.tag) != name:
            continue
        text = "".join(child.itertext()).strip()
        if text:
            return text
    return None


def _xml_child_attr(el: ET.Element, name: str, attr: str) -> str | None:
    for child in list(el):
        if _localname(child.tag) == name:
            value = child.attrib.get(attr)
            if isinstance(value, str) and value.strip():
                return value
    return None


def _cda_effective_start_end(el: ET.Element) -> tuple[str | None, str | None]:
    for child in list(el):
        if _localname(child.tag) != "effectiveTime":
            continue
        direct_value = child.attrib.get("value")
        if isinstance(direct_value, str) and direct_value.strip():
            t = _normalize_time(direct_value)
            return t, t
        low = None
        high = None
        for grand in list(child):
            ln = _localname(grand.tag)
            v = grand.attrib.get("value")
            if not isinstance(v, str):
                continue
            if ln == "low":
                low = _normalize_time(v)
            elif ln == "high":
                high = _normalize_time(v)
        return low, high
    return None, None


def _export_cda_streams(ctx: ExportContext) -> tuple[list[dict], list[dict]]:
    if not ctx.export_cda_rel:
        return [], []
    path = ctx.root_dir / ctx.export_cda_rel
    if not path.exists():
        return [], []

    observations: list[dict] = []
    encounters: list[dict] = []

    root = ET.parse(path).getroot()

    # Section-level rows provide deterministic, share-safe discharge summary context.
    sections = [el for el in root.iter() if _localname(el.tag) == "section"]
    task_sections = progress.task("Parse export_cda.xml sections", total=len(sections), unit="sections")
    for section in sections:
        section_code = _xml_child_attr(section, "code", "code")
        section_display = _xml_child_attr(section, "code", "displayName")
        section_title = _xml_child_text(section, "title")
        section_time = _normalize_time(_xml_child_attr(section, "effectiveTime", "value"))

        if section_code or section_title or section_display:
            base = {
                "schema_version": 2,
                "canonical_person_id": _canonical_person_id(ctx),
                "source": "cda",
                "source_system": _source_system_tag("cda:export_cda.xml"),
                "source_file": _safe_relpath(ctx.export_cda_rel),
                "event_time": section_time,
                "run_id": ctx.run_id,
                "resource_type": "CDASection",
                "section_code": section_code,
                "section_display": section_display,
                "section_title": section_title,
            }
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            observations.append(base)

        for observation in [el for el in section.iter() if _localname(el.tag) == "observation"]:
            effective_time = _normalize_time(_xml_child_attr(observation, "effectiveTime", "value"))
            code_code = _xml_child_attr(observation, "code", "code")
            code_display = _xml_child_attr(observation, "code", "displayName")
            value_val = _xml_child_attr(observation, "value", "value")
            value_unit = _xml_child_attr(observation, "value", "unit")

            base = {
                "schema_version": 2,
                "canonical_person_id": _canonical_person_id(ctx),
                "source": "cda",
                "source_system": _source_system_tag("cda:export_cda.xml"),
                "source_file": _safe_relpath(ctx.export_cda_rel),
                "event_time": effective_time,
                "run_id": ctx.run_id,
                "resource_type": "CDAObservation",
                "section_code": section_code,
                "section_display": section_display,
                "section_title": section_title,
                "code": code_code,
                "value": value_val,
                "unit": value_unit,
            }
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            observations.append(base)
        task_sections.advance(1)

    # Encounter-like rows from discharge/service-event timing.
    encounter_like = [
        el
        for el in root.iter()
        if _localname(el.tag) in {"encompassingEncounter", "serviceEvent"}
    ]
    task_enc = progress.task("Parse export_cda.xml encounter timing", total=len(encounter_like), unit="rows")
    for el in encounter_like:
        start, end = _cda_effective_start_end(el)
        event_time = start or end
        if event_time:
            base = {
                "schema_version": 2,
                "canonical_person_id": _canonical_person_id(ctx),
                "source": "cda",
                "source_system": _source_system_tag("cda:export_cda.xml"),
                "source_file": _safe_relpath(ctx.export_cda_rel),
                "event_time": event_time,
                "run_id": ctx.run_id,
                "resource_type": "CDAEncounter",
                "start_time": start,
                "end_time": end,
            }
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            encounters.append(base)
        task_enc.advance(1)

    return observations, encounters


def export_ndjson(*, input_dir: str, out_dir: str, mode: str = "local") -> None:
    with progress.phase("export: resolve context"):
        ctx = _resolve_context(input_dir=Path(input_dir), mode=mode)

    with progress.phase("export: parse HealthKit"):
        healthkit_obs = _export_healthkit_observations(ctx)
    with progress.phase("export: parse FHIR"):
        (
            fhir_obs,
            fhir_docs,
            fhir_meds,
            fhir_conds,
            fhir_encounters,
            fhir_procedures,
            fhir_reports,
        ) = _export_fhir_streams(ctx)
    with progress.phase("export: parse CDA"):
        cda_obs, cda_encounters = _export_cda_streams(ctx)

    observations = [*healthkit_obs, *fhir_obs, *cda_obs]
    documents = [*fhir_docs]
    meds = [*fhir_meds]
    conds = [*fhir_conds]
    encounters = [*fhir_encounters, *cda_encounters]
    procedures = [*fhir_procedures]
    diagnostic_reports = [*fhir_reports]

    def dedupe(rows: list[dict]) -> list[dict]:
        seen: set[str] = set()
        out: list[dict] = []
        for r in rows:
            k = r.get("event_key")
            if not isinstance(k, str):
                k = _sha256_bytes(json.dumps(r, sort_keys=True, separators=(",", ":")).encode("utf-8"))
                r["event_key"] = k
            if k in seen:
                continue
            seen.add(k)
            out.append(r)
        return out

    def sort_rows(rows: list[dict]) -> list[dict]:
        def key(r: dict) -> tuple:
            return (
                r.get("event_time") or "",
                r.get("canonical_person_id") or "",
                r.get("source") or "",
                r.get("source_file") or "",
                r.get("source_id") or "",
                r.get("event_key") or "",
            )

        return sorted(rows, key=key)

    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    with progress.phase("export: dedupe + sort"):
        observations = sort_rows(dedupe(observations))
        documents = sort_rows(dedupe(documents))
        meds = sort_rows(dedupe(meds))
        conds = sort_rows(dedupe(conds))
        encounters = sort_rows(dedupe(encounters))
        procedures = sort_rows(dedupe(procedures))
        diagnostic_reports = sort_rows(dedupe(diagnostic_reports))

    with progress.phase("export: write ndjson"):
        _write_ndjson(out_root / "observations.ndjson", observations)
        _write_ndjson(out_root / "documents.ndjson", documents)
        if meds:
            _write_ndjson(out_root / "medications.ndjson", meds)
        if conds:
            _write_ndjson(out_root / "conditions.ndjson", conds)
        if encounters:
            _write_ndjson(out_root / "encounters.ndjson", encounters)
        if procedures:
            _write_ndjson(out_root / "procedures.ndjson", procedures)
        if diagnostic_reports:
            _write_ndjson(out_root / "diagnostic_reports.ndjson", diagnostic_reports)
