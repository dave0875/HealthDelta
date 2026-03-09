from __future__ import annotations

import base64
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
    beneficiary = resource.get("beneficiary")
    if isinstance(beneficiary, dict):
        ref = beneficiary.get("reference")
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
    beneficiary = resource.get("beneficiary")
    if isinstance(beneficiary, dict):
        ident = beneficiary.get("identifier")
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


def _sorted_string_list(values: list[str]) -> list[str]:
    return sorted({value.strip() for value in values if isinstance(value, str) and value.strip()})


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
    if rt == "Goal":
        start_date = resource.get("startDate")
        if isinstance(start_date, str):
            return _normalize_time(start_date)
        targets = resource.get("target")
        if isinstance(targets, list):
            for target in targets:
                if not isinstance(target, dict):
                    continue
                due_date = target.get("dueDate")
                if isinstance(due_date, str):
                    return _normalize_time(due_date)
    if rt == "CarePlan":
        period = resource.get("period")
        if isinstance(period, dict):
            start = period.get("start")
            if isinstance(start, str):
                return _normalize_time(start)
            end = period.get("end")
            if isinstance(end, str):
                return _normalize_time(end)
        created = resource.get("created")
        if isinstance(created, str):
            return _normalize_time(created)
    if rt == "ServiceRequest":
        authored_on = resource.get("authoredOn")
        if isinstance(authored_on, str):
            return _normalize_time(authored_on)
    if rt == "Coverage":
        period = resource.get("period")
        if isinstance(period, dict):
            start = period.get("start")
            if isinstance(start, str):
                return _normalize_time(start)
            end = period.get("end")
            if isinstance(end, str):
                return _normalize_time(end)
    if rt == "ImagingStudy":
        started = resource.get("started")
        if isinstance(started, str):
            return _normalize_time(started)
    if rt == "Specimen":
        collection = resource.get("collection")
        if isinstance(collection, dict):
            collected = collection.get("collectedDateTime")
            if isinstance(collected, str):
                return _normalize_time(collected)
            collected_period = collection.get("collectedPeriod")
            if isinstance(collected_period, dict):
                start = collected_period.get("start")
                if isinstance(start, str):
                    return _normalize_time(start)
                end = collected_period.get("end")
                if isinstance(end, str):
                    return _normalize_time(end)
        received = resource.get("receivedTime")
        if isinstance(received, str):
            return _normalize_time(received)
    if rt == "Provenance":
        recorded = resource.get("recorded")
        if isinstance(recorded, str):
            return _normalize_time(recorded)
    return None


def _export_fhir_streams(
    ctx: ExportContext,
) -> tuple[
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
]:
    observations: list[dict] = []
    documents: list[dict] = []
    binaries: list[dict] = []
    meds: list[dict] = []
    conds: list[dict] = []
    encounters: list[dict] = []
    procedures: list[dict] = []
    diagnostic_reports: list[dict] = []
    goals: list[dict] = []
    careplans: list[dict] = []
    service_requests: list[dict] = []
    coverages: list[dict] = []
    organizations: list[dict] = []
    practitioners: list[dict] = []
    locations: list[dict] = []
    imaging_studies: list[dict] = []
    specimens: list[dict] = []
    devices: list[dict] = []
    provenance_rows: list[dict] = []
    observation_keys: dict[str, str] = {}
    source_record_keys: dict[str, str] = {}
    pending_report_links: list[tuple[dict, list[str]]] = []
    pending_provenance_links: list[tuple[dict, list[str]]] = []
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

        def register_source_record_key(row: dict) -> None:
            source_id = row.get("source_id")
            record_key = row.get("record_key")
            if isinstance(source_id, str) and source_id and isinstance(record_key, str) and record_key:
                source_record_keys[source_id] = record_key

        if rt == "Observation":
            if rid:
                base["record_id"] = rid
                base["observation_id"] = rid
            base["record_type"] = "Observation"
            subject = res.get("subject")
            if isinstance(subject, dict):
                subject_reference = subject.get("reference")
                if isinstance(subject_reference, str) and subject_reference.strip():
                    base["subject_reference"] = subject_reference.strip()
            encounter = res.get("encounter")
            if isinstance(encounter, dict):
                encounter_reference = encounter.get("reference")
                if isinstance(encounter_reference, str) and encounter_reference.strip():
                    encounter_id = _extract_fhir_reference_id(encounter_reference, "Encounter")
                    if encounter_id:
                        base["encounter_id"] = encounter_id
            effective = res.get("effectivePeriod")
            if isinstance(effective, dict):
                start = effective.get("start")
                end = effective.get("end")
                base["effective_start"] = _normalize_time(start) if isinstance(start, str) else None
                base["effective_end"] = _normalize_time(end) if isinstance(end, str) else None
            else:
                effective_dt = res.get("effectiveDateTime")
                normalized = _normalize_time(effective_dt) if isinstance(effective_dt, str) else None
                base["effective_start"] = normalized
                base["effective_end"] = normalized
            code = res.get("code")
            if isinstance(code, dict):
                base["code_system"] = _first_fhir_coding_value(code, "system")
                code_value = _first_fhir_coding_value(code, "code")
                if code_value is not None:
                    base["code"] = code_value
                display = _first_fhir_coding_value(code, "display")
                if display is None:
                    text = code.get("text")
                    if isinstance(text, str) and text.strip():
                        display = text.strip()
                base["display"] = display
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
            components = res.get("component")
            if isinstance(components, list):
                component_rows: list[dict[str, object]] = []
                for component in components:
                    if not isinstance(component, dict):
                        continue
                    row: dict[str, object] = {}
                    component_code = component.get("code")
                    if isinstance(component_code, dict):
                        code_system = _first_fhir_coding_value(component_code, "system")
                        code_value = _first_fhir_coding_value(component_code, "code")
                        display = _first_fhir_coding_value(component_code, "display")
                        if display is None:
                            text = component_code.get("text")
                            if isinstance(text, str) and text.strip():
                                display = text.strip()
                        if code_system is not None:
                            row["code_system"] = code_system
                        if code_value is not None:
                            row["code"] = code_value
                        if display is not None:
                            row["display"] = display
                    value_quantity = component.get("valueQuantity")
                    if isinstance(value_quantity, dict):
                        if "value" in value_quantity:
                            row["value"] = value_quantity["value"]
                        unit = value_quantity.get("unit")
                        if isinstance(unit, str) and unit.strip():
                            row["unit"] = unit.strip()
                    if row:
                        component_rows.append(row)
                if component_rows:
                    base["components"] = sorted(
                        component_rows,
                        key=lambda item: (
                            str(item.get("code_system") or ""),
                            str(item.get("code") or ""),
                            str(item.get("display") or ""),
                            str(item.get("value") if item.get("value") is not None else ""),
                            str(item.get("unit") or ""),
                        ),
                    )
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
            register_source_record_key(base)
        elif rt == "DocumentReference":
            if rid:
                base["record_id"] = rid
                base["document_reference_id"] = rid
            base["record_type"] = "DocumentReference"
            subject = res.get("subject")
            if isinstance(subject, dict):
                subject_reference = subject.get("reference")
                if isinstance(subject_reference, str) and subject_reference.strip():
                    base["subject_reference"] = subject_reference.strip()
            t = res.get("type")
            if isinstance(t, dict):
                base["type_system"] = _first_fhir_coding_value(t, "system")
                base["type_code"] = _first_fhir_coding_value(t, "code")
                display = _first_fhir_coding_value(t, "display")
                if display is None:
                    text = t.get("text")
                    if isinstance(text, str) and text.strip():
                        display = text.strip()
                base["display"] = display
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
            content = res.get("content")
            if isinstance(content, list):
                attachments: list[dict[str, object]] = []
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    attachment = item.get("attachment")
                    if not isinstance(attachment, dict):
                        continue
                    row: dict[str, object] = {}
                    content_type = attachment.get("contentType")
                    if isinstance(content_type, str) and content_type.strip():
                        row["content_type"] = content_type.strip()
                    title = attachment.get("title")
                    if isinstance(title, str) and title.strip():
                        row["title"] = title.strip()
                    size = attachment.get("size")
                    if isinstance(size, int):
                        row["size"] = size
                    hash_value = attachment.get("hash")
                    if isinstance(hash_value, str) and hash_value.strip():
                        row["hash"] = hash_value.strip()
                    binary_id = _extract_fhir_reference_id(attachment.get("url"), "Binary")
                    if binary_id:
                        row["binary_id"] = binary_id
                    if row:
                        attachments.append(row)
                if attachments:
                    base["attachments"] = sorted(
                        attachments,
                        key=lambda item: (
                            str(item.get("content_type") or ""),
                            str(item.get("title") or ""),
                            int(item.get("size") or 0),
                            str(item.get("hash") or ""),
                        ),
                    )
            status = res.get("status")
            if isinstance(status, str):
                base["status"] = status
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            documents.append(base)
            register_source_record_key(base)
        elif rt == "Binary":
            if rid:
                base["record_id"] = rid
                base["binary_id"] = rid
            base["record_type"] = "Binary"
            base["event_time"] = base.get("event_time") or ""
            content_type = res.get("contentType")
            if isinstance(content_type, str) and content_type.strip():
                base["content_type"] = content_type.strip()
            security_context = res.get("securityContext")
            if isinstance(security_context, dict):
                security_context_reference = security_context.get("reference")
                if isinstance(security_context_reference, str) and security_context_reference.strip():
                    base["security_context_reference"] = security_context_reference.strip()
            data = res.get("data")
            if isinstance(data, str) and data.strip():
                try:
                    decoded = base64.b64decode(data.encode("utf-8"), validate=True)
                except Exception:
                    decoded = data.encode("utf-8")
                base["content_size_bytes"] = len(decoded)
                base["content_sha256"] = _sha256_bytes(decoded)
                base["data_present"] = True
            else:
                base["data_present"] = False
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            binaries.append(base)
            register_source_record_key(base)
        elif rt in {"MedicationRequest", "MedicationStatement", "MedicationDispense"}:
            if rid:
                base["record_id"] = rid
            base["record_type"] = rt
            subject = res.get("subject")
            if isinstance(subject, dict):
                subject_reference = subject.get("reference")
                if isinstance(subject_reference, str) and subject_reference.strip():
                    base["subject_reference"] = subject_reference.strip()
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
            register_source_record_key(base)
        elif rt in {"Condition", "AllergyIntolerance"}:
            if rid:
                base["record_id"] = rid
            base["record_type"] = rt
            subject = res.get("subject")
            if isinstance(subject, dict):
                subject_reference = subject.get("reference")
                if isinstance(subject_reference, str) and subject_reference.strip():
                    base["subject_reference"] = subject_reference.strip()
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
            register_source_record_key(base)
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
            register_source_record_key(base)
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
            register_source_record_key(base)
        elif rt == "Procedure":
            if rid:
                base["record_id"] = rid
            base["record_type"] = "Procedure"
            subject = res.get("subject")
            if isinstance(subject, dict):
                subject_reference = subject.get("reference")
                if isinstance(subject_reference, str) and subject_reference.strip():
                    base["subject_reference"] = subject_reference.strip()
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
            register_source_record_key(base)
        elif rt == "DiagnosticReport":
            if rid:
                base["record_id"] = rid
                base["diagnostic_report_id"] = rid
            base["record_type"] = "DiagnosticReport"
            subject = res.get("subject")
            if isinstance(subject, dict):
                subject_reference = subject.get("reference")
                if isinstance(subject_reference, str) and subject_reference.strip():
                    base["subject_reference"] = subject_reference.strip()
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
            effective = res.get("effectivePeriod")
            if isinstance(effective, dict):
                start = effective.get("start")
                end = effective.get("end")
                base["effective_start"] = _normalize_time(start) if isinstance(start, str) else None
                base["effective_end"] = _normalize_time(end) if isinstance(end, str) else None
            else:
                effective_dt = res.get("effectiveDateTime")
                normalized = _normalize_time(effective_dt) if isinstance(effective_dt, str) else None
                if normalized is not None:
                    base["effective_start"] = normalized
                    base["effective_end"] = normalized
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
            presented_form = res.get("presentedForm")
            if isinstance(presented_form, list):
                attachments: list[dict[str, object]] = []
                for item in presented_form:
                    if not isinstance(item, dict):
                        continue
                    row: dict[str, object] = {}
                    content_type = item.get("contentType")
                    if isinstance(content_type, str) and content_type.strip():
                        row["content_type"] = content_type.strip()
                    title = item.get("title")
                    if isinstance(title, str) and title.strip():
                        row["title"] = title.strip()
                    size = item.get("size")
                    if isinstance(size, int):
                        row["size"] = size
                    hash_value = item.get("hash")
                    if isinstance(hash_value, str) and hash_value.strip():
                        row["hash"] = hash_value.strip()
                    binary_id = _extract_fhir_reference_id(item.get("url"), "Binary")
                    if binary_id:
                        row["binary_id"] = binary_id
                    if row:
                        attachments.append(row)
                if attachments:
                    base["presented_forms"] = sorted(
                        attachments,
                        key=lambda item: (
                            str(item.get("content_type") or ""),
                            str(item.get("title") or ""),
                            int(item.get("size") or 0),
                            str(item.get("hash") or ""),
                            str(item.get("binary_id") or ""),
                        ),
                    )
            diagnostic_reports.append(base)
        elif rt == "Goal":
            if rid:
                base["record_id"] = rid
                base["goal_id"] = rid
            base["record_type"] = "Goal"
            subject = res.get("subject")
            if isinstance(subject, dict):
                subject_reference = subject.get("reference")
                if isinstance(subject_reference, str) and subject_reference.strip():
                    base["subject_reference"] = subject_reference.strip()
            status = res.get("lifecycleStatus")
            if isinstance(status, str):
                base["status"] = status
            start_date = res.get("startDate")
            if isinstance(start_date, str) and start_date.strip():
                base["start_date"] = start_date.strip()
            targets = res.get("target")
            if isinstance(targets, list):
                for target in targets:
                    if not isinstance(target, dict):
                        continue
                    due_date = target.get("dueDate")
                    if isinstance(due_date, str) and due_date.strip():
                        base["target_due_date"] = due_date.strip()
                        break
            description = res.get("description")
            if isinstance(description, dict):
                text = description.get("text")
                if isinstance(text, str) and text.strip():
                    base["description"] = text.strip()
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            goals.append(base)
            register_source_record_key(base)
        elif rt == "CarePlan":
            if rid:
                base["record_id"] = rid
                base["careplan_id"] = rid
            base["record_type"] = "CarePlan"
            subject = res.get("subject")
            if isinstance(subject, dict):
                subject_reference = subject.get("reference")
                if isinstance(subject_reference, str) and subject_reference.strip():
                    base["subject_reference"] = subject_reference.strip()
            status = res.get("status")
            if isinstance(status, str):
                base["status"] = status
            intent = res.get("intent")
            if isinstance(intent, str):
                base["intent"] = intent
            period = res.get("period")
            if isinstance(period, dict):
                start = period.get("start")
                end = period.get("end")
                base["period_start"] = _normalize_time(start) if isinstance(start, str) else None
                base["period_end"] = _normalize_time(end) if isinstance(end, str) else None
            goal_refs = res.get("goal")
            if isinstance(goal_refs, list):
                goal_ids = sorted(
                    {
                        goal_id
                        for item in goal_refs
                        if isinstance(item, dict)
                        for goal_id in [_extract_fhir_reference_id(item.get("reference"), "Goal")]
                        if goal_id
                    }
                )
                if goal_ids:
                    base["goal_ids"] = goal_ids
            title = res.get("title")
            if isinstance(title, str) and title.strip():
                base["title"] = title.strip()
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            careplans.append(base)
            register_source_record_key(base)
        elif rt == "ServiceRequest":
            if rid:
                base["record_id"] = rid
                base["service_request_id"] = rid
            base["record_type"] = "ServiceRequest"
            subject = res.get("subject")
            if isinstance(subject, dict):
                subject_reference = subject.get("reference")
                if isinstance(subject_reference, str) and subject_reference.strip():
                    base["subject_reference"] = subject_reference.strip()
            status = res.get("status")
            if isinstance(status, str):
                base["status"] = status
            intent = res.get("intent")
            if isinstance(intent, str):
                base["intent"] = intent
            authored_on = res.get("authoredOn")
            if isinstance(authored_on, str) and authored_on.strip():
                base["authored_on"] = _normalize_time(authored_on)
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
            performer = res.get("performer")
            if isinstance(performer, list):
                performer_references = sorted(
                    {
                        reference.strip()
                        for item in performer
                        if isinstance(item, dict)
                        for reference in [item.get("reference")]
                        if isinstance(reference, str) and reference.strip()
                    }
                )
                if performer_references:
                    base["performer_references"] = performer_references
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            service_requests.append(base)
            register_source_record_key(base)
        elif rt == "Coverage":
            if rid:
                base["record_id"] = rid
                base["coverage_id"] = rid
            base["record_type"] = "Coverage"
            beneficiary = res.get("beneficiary")
            if isinstance(beneficiary, dict):
                subject_reference = beneficiary.get("reference")
                if isinstance(subject_reference, str) and subject_reference.strip():
                    base["subject_reference"] = subject_reference.strip()
            status = res.get("status")
            if isinstance(status, str):
                base["status"] = status
            cov_type = res.get("type")
            if isinstance(cov_type, dict):
                base["type_system"] = _first_fhir_coding_value(cov_type, "system")
                base["type_code"] = _first_fhir_coding_value(cov_type, "code")
            relationship = res.get("relationship")
            if isinstance(relationship, dict):
                relationship_code = _first_fhir_coding_value(relationship, "code")
                if relationship_code is not None:
                    base["subscriber_relationship"] = relationship_code
            period = res.get("period")
            if isinstance(period, dict):
                start = period.get("start")
                end = period.get("end")
                base["period_start"] = _normalize_time(start) if isinstance(start, str) else None
                base["period_end"] = _normalize_time(end) if isinstance(end, str) else None
            payor = res.get("payor")
            if isinstance(payor, list):
                payor_references = sorted(
                    {
                        reference.strip()
                        for item in payor
                        if isinstance(item, dict)
                        for reference in [item.get("reference")]
                        if isinstance(reference, str) and reference.strip()
                    }
                )
                if payor_references:
                    base["payor_references"] = payor_references
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            coverages.append(base)
            register_source_record_key(base)
        elif rt == "Organization":
            if rid:
                base["record_id"] = rid
                base["organization_id"] = rid
            base["record_type"] = "Organization"
            name = res.get("name")
            if isinstance(name, str) and name.strip():
                base["name"] = name.strip()
            org_type = res.get("type")
            if isinstance(org_type, list) and org_type:
                first = org_type[0]
                if isinstance(first, dict):
                    base["type_system"] = _first_fhir_coding_value(first, "system")
                    base["type_code"] = _first_fhir_coding_value(first, "code")
            address = res.get("address")
            if isinstance(address, list) and address:
                first_address = address[0]
                if isinstance(first_address, dict):
                    city = first_address.get("city")
                    state = first_address.get("state")
                    postal_code = first_address.get("postalCode")
                    if isinstance(city, str) and city.strip():
                        base["address_city"] = city.strip()
                    if isinstance(state, str) and state.strip():
                        base["address_state"] = state.strip()
                    if isinstance(postal_code, str) and postal_code.strip():
                        base["address_postal_code"] = postal_code.strip()
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            organizations.append(base)
            register_source_record_key(base)
        elif rt == "Practitioner":
            if rid:
                base["record_id"] = rid
                base["practitioner_id"] = rid
            base["record_type"] = "Practitioner"
            names = res.get("name")
            if isinstance(names, list) and names:
                first_name = names[0]
                if isinstance(first_name, dict):
                    text = first_name.get("text")
                    if isinstance(text, str) and text.strip():
                        base["name"] = text.strip()
            identifiers = res.get("identifier")
            if isinstance(identifiers, list) and identifiers:
                first_identifier = identifiers[0]
                if isinstance(first_identifier, dict):
                    system = first_identifier.get("system")
                    value = first_identifier.get("value")
                    if isinstance(system, str) and system.strip():
                        base["identifier_system"] = system.strip()
                    if isinstance(value, str) and value.strip():
                        base["identifier_value"] = value.strip()
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            practitioners.append(base)
            register_source_record_key(base)
        elif rt == "Location":
            if rid:
                base["record_id"] = rid
                base["location_id"] = rid
            base["record_type"] = "Location"
            name = res.get("name")
            if isinstance(name, str) and name.strip():
                base["name"] = name.strip()
            address = res.get("address")
            if isinstance(address, dict):
                city = address.get("city")
                state = address.get("state")
                postal_code = address.get("postalCode")
                if isinstance(city, str) and city.strip():
                    base["address_city"] = city.strip()
                if isinstance(state, str) and state.strip():
                    base["address_state"] = state.strip()
                if isinstance(postal_code, str) and postal_code.strip():
                    base["address_postal_code"] = postal_code.strip()
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            locations.append(base)
            register_source_record_key(base)
        elif rt == "ImagingStudy":
            if rid:
                base["record_id"] = rid
                base["imaging_study_id"] = rid
            base["record_type"] = "ImagingStudy"
            subject = res.get("subject")
            if isinstance(subject, dict):
                subject_reference = subject.get("reference")
                if isinstance(subject_reference, str) and subject_reference.strip():
                    base["subject_reference"] = subject_reference.strip()
            status = res.get("status")
            if isinstance(status, str) and status.strip():
                base["status"] = status.strip()
            started = res.get("started")
            if isinstance(started, str) and started.strip():
                base["started"] = _normalize_time(started)
            series = res.get("series")
            if isinstance(series, list):
                summaries: list[dict[str, object]] = []
                for item in series:
                    if not isinstance(item, dict):
                        continue
                    row: dict[str, object] = {}
                    modality = item.get("modality")
                    if isinstance(modality, dict):
                        system = modality.get("system")
                        code = modality.get("code")
                        if isinstance(system, str) and system.strip():
                            row["modality_system"] = system.strip()
                        if isinstance(code, str) and code.strip():
                            row["modality_code"] = code.strip()
                    body_site = item.get("bodySite")
                    if isinstance(body_site, dict):
                        system = body_site.get("system")
                        code = body_site.get("code")
                        if isinstance(system, str) and system.strip():
                            row["body_site_system"] = system.strip()
                        if isinstance(code, str) and code.strip():
                            row["body_site_code"] = code.strip()
                    instances = item.get("instance")
                    if isinstance(instances, list):
                        row["instance_count"] = len([inst for inst in instances if isinstance(inst, dict)])
                    if row:
                        summaries.append(row)
                if summaries:
                    base["series_summary"] = sorted(
                        summaries,
                        key=lambda item: (
                            str(item.get("modality_system") or ""),
                            str(item.get("modality_code") or ""),
                            str(item.get("body_site_system") or ""),
                            str(item.get("body_site_code") or ""),
                            int(item.get("instance_count") or 0),
                        ),
                    )
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            imaging_studies.append(base)
            register_source_record_key(base)
        elif rt == "Specimen":
            if rid:
                base["record_id"] = rid
                base["specimen_id"] = rid
            base["record_type"] = "Specimen"
            subject = res.get("subject")
            if isinstance(subject, dict):
                subject_reference = subject.get("reference")
                if isinstance(subject_reference, str) and subject_reference.strip():
                    base["subject_reference"] = subject_reference.strip()
            collection = res.get("collection")
            if isinstance(collection, dict):
                collected = collection.get("collectedDateTime")
                if isinstance(collected, str) and collected.strip():
                    base["collected_time"] = _normalize_time(collected)
                else:
                    collected_period = collection.get("collectedPeriod")
                    if isinstance(collected_period, dict):
                        start = collected_period.get("start")
                        end = collected_period.get("end")
                        if isinstance(start, str) and start.strip():
                            base["collected_time"] = _normalize_time(start)
                        elif isinstance(end, str) and end.strip():
                            base["collected_time"] = _normalize_time(end)
            received_time = res.get("receivedTime")
            if isinstance(received_time, str) and received_time.strip():
                base["received_time"] = _normalize_time(received_time)
            specimen_type = res.get("type")
            if isinstance(specimen_type, dict):
                base["type_system"] = _first_fhir_coding_value(specimen_type, "system")
                base["type_code"] = _first_fhir_coding_value(specimen_type, "code")
                display = _first_fhir_coding_value(specimen_type, "display")
                if display is None:
                    text = specimen_type.get("text")
                    if isinstance(text, str) and text.strip():
                        display = text.strip()
                base["display"] = display
            identifiers = _extract_identifier_pairs(res.get("identifier"))
            if identifiers:
                base["identifiers"] = [{"system": system, "value": value} for system, value in identifiers]
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            specimens.append(base)
            register_source_record_key(base)
        elif rt == "Device":
            if rid:
                base["record_id"] = rid
                base["device_id"] = rid
            base["record_type"] = "Device"
            base["event_time"] = base.get("event_time") or ""
            patient = res.get("patient")
            if isinstance(patient, dict):
                patient_reference = patient.get("reference")
                if isinstance(patient_reference, str) and patient_reference.strip():
                    base["patient_reference"] = patient_reference.strip()
            status = res.get("status")
            if isinstance(status, str) and status.strip():
                base["status"] = status.strip()
            device_type = res.get("type")
            if isinstance(device_type, dict):
                base["type_system"] = _first_fhir_coding_value(device_type, "system")
                base["type_code"] = _first_fhir_coding_value(device_type, "code")
                display = _first_fhir_coding_value(device_type, "display")
                if display is None:
                    text = device_type.get("text")
                    if isinstance(text, str) and text.strip():
                        display = text.strip()
                base["display"] = display
            manufacturer = res.get("manufacturer")
            if isinstance(manufacturer, str) and manufacturer.strip():
                base["manufacturer"] = manufacturer.strip()
            identifiers = _extract_identifier_pairs(res.get("identifier"))
            if identifiers:
                base["identifiers"] = [{"system": system, "value": value} for system, value in identifiers]
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            base["record_key"] = base["event_key"]
            devices.append(base)
            register_source_record_key(base)
        elif rt == "Provenance":
            if rid:
                base["record_id"] = rid
                base["provenance_id"] = rid
            base["record_type"] = "Provenance"
            recorded = res.get("recorded")
            if isinstance(recorded, str) and recorded.strip():
                base["recorded"] = _normalize_time(recorded)
            agents = res.get("agent")
            if isinstance(agents, list):
                agent_references = _sorted_string_list(
                    [
                        who.get("reference")
                        for agent in agents
                        if isinstance(agent, dict)
                        for who in [agent.get("who")]
                        if isinstance(who, dict)
                    ]
                )
                if agent_references:
                    base["agent_references"] = agent_references
            targets = res.get("target")
            if isinstance(targets, list):
                target_references = _sorted_string_list(
                    [
                        reference
                        for item in targets
                        if isinstance(item, dict)
                        for reference in [item.get("reference")]
                        if isinstance(reference, str)
                    ]
                )
                if target_references:
                    base["target_references"] = target_references
                    resolved_target_keys = sorted(
                        {source_record_keys[reference] for reference in target_references if reference in source_record_keys}
                    )
                    if resolved_target_keys:
                        base["target_record_keys"] = resolved_target_keys
                    if len(resolved_target_keys) != len(target_references):
                        pending_provenance_links.append((base, target_references))
            provenance_rows.append(base)
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
        register_source_record_key(report)

    if pending_provenance_links:
        for provenance, refs in pending_provenance_links:
            resolved = sorted({source_record_keys[ref] for ref in refs if ref in source_record_keys})
            if resolved:
                provenance["target_record_keys"] = resolved

    for provenance in provenance_rows:
        provenance["event_key"] = _sha256_bytes(
            json.dumps(provenance, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        provenance["record_key"] = provenance["event_key"]
        register_source_record_key(provenance)

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

    return (
        observations,
        documents,
        binaries,
        meds,
        conds,
        encounters,
        procedures,
        diagnostic_reports,
        goals,
        careplans,
        service_requests,
        coverages,
        organizations,
        practitioners,
        locations,
        imaging_studies,
        specimens,
        devices,
        provenance_rows,
    )


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
            fhir_binaries,
            fhir_meds,
            fhir_conds,
            fhir_encounters,
            fhir_procedures,
            fhir_reports,
            fhir_goals,
            fhir_careplans,
            fhir_service_requests,
            fhir_coverages,
            fhir_organizations,
            fhir_practitioners,
            fhir_locations,
            fhir_imaging_studies,
            fhir_specimens,
            fhir_devices,
            fhir_provenance,
        ) = _export_fhir_streams(ctx)
    with progress.phase("export: parse CDA"):
        cda_obs, cda_encounters = _export_cda_streams(ctx)

    observations = [*healthkit_obs, *fhir_obs, *cda_obs]
    documents = [*fhir_docs]
    binaries = [*fhir_binaries]
    meds = [*fhir_meds]
    conds = [*fhir_conds]
    encounters = [*fhir_encounters, *cda_encounters]
    procedures = [*fhir_procedures]
    diagnostic_reports = [*fhir_reports]
    goals = [*fhir_goals]
    careplans = [*fhir_careplans]
    service_requests = [*fhir_service_requests]
    coverages = [*fhir_coverages]
    organizations = [*fhir_organizations]
    practitioners = [*fhir_practitioners]
    locations = [*fhir_locations]
    imaging_studies = [*fhir_imaging_studies]
    specimens = [*fhir_specimens]
    devices = [*fhir_devices]
    provenance_rows = [*fhir_provenance]

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
        binaries = sort_rows(dedupe(binaries))
        meds = sort_rows(dedupe(meds))
        conds = sort_rows(dedupe(conds))
        encounters = sort_rows(dedupe(encounters))
        procedures = sort_rows(dedupe(procedures))
        diagnostic_reports = sort_rows(dedupe(diagnostic_reports))
        goals = sort_rows(dedupe(goals))
        careplans = sort_rows(dedupe(careplans))
        service_requests = sort_rows(dedupe(service_requests))
        coverages = sort_rows(dedupe(coverages))
        organizations = sort_rows(dedupe(organizations))
        practitioners = sort_rows(dedupe(practitioners))
        locations = sort_rows(dedupe(locations))
        imaging_studies = sort_rows(dedupe(imaging_studies))
        specimens = sort_rows(dedupe(specimens))
        devices = sort_rows(dedupe(devices))
        provenance_rows = sort_rows(dedupe(provenance_rows))

    with progress.phase("export: write ndjson"):
        _write_ndjson(out_root / "observations.ndjson", observations)
        _write_ndjson(out_root / "documents.ndjson", documents)
        if binaries:
            _write_ndjson(out_root / "binaries.ndjson", binaries)
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
        if goals:
            _write_ndjson(out_root / "goals.ndjson", goals)
        if careplans:
            _write_ndjson(out_root / "careplans.ndjson", careplans)
        if service_requests:
            _write_ndjson(out_root / "service_requests.ndjson", service_requests)
        if coverages:
            _write_ndjson(out_root / "coverages.ndjson", coverages)
        if organizations:
            _write_ndjson(out_root / "organizations.ndjson", organizations)
        if practitioners:
            _write_ndjson(out_root / "practitioners.ndjson", practitioners)
        if locations:
            _write_ndjson(out_root / "locations.ndjson", locations)
        if imaging_studies:
            _write_ndjson(out_root / "imaging_studies.ndjson", imaging_studies)
        if specimens:
            _write_ndjson(out_root / "specimens.ndjson", specimens)
        if devices:
            _write_ndjson(out_root / "devices.ndjson", devices)
        if provenance_rows:
            _write_ndjson(out_root / "provenance.ndjson", provenance_rows)
