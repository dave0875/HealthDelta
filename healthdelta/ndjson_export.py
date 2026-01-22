from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _write_ndjson(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent)) as tf:
        tmp = Path(tf.name)
        for row in rows:
            tf.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
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
            "canonical_person_id": _canonical_person_id(ctx),
            "source": "healthkit",
            "source_file": _safe_relpath(ctx.export_xml_rel),
            "event_time": event_time,
            "run_id": ctx.run_id,
            "hk_type": hk_type,
            "value": value,
            "unit": unit,
        }
        minimal["event_key"] = _sha256_bytes(json.dumps(minimal, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        observations.append(minimal)
        el.clear()

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
    if rt == "Condition":
        t = resource.get("recordedDate")
        if isinstance(t, str):
            return _normalize_time(t)
        onset = resource.get("onsetDateTime")
        if isinstance(onset, str):
            return _normalize_time(onset)
    return None


def _export_fhir_streams(ctx: ExportContext) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    observations: list[dict] = []
    documents: list[dict] = []
    meds: list[dict] = []
    conds: list[dict] = []

    for rel, res in _walk_source_fhir_files(ctx):
        rt = res.get("resourceType")
        if not isinstance(rt, str):
            continue

        # Patient resources are used only for identity mapping; do not emit them.
        if rt == "Patient":
            continue

        rid = res.get("id") if isinstance(res.get("id"), str) else None
        subject_patient_id = _extract_fhir_subject_patient_id(res)
        person = _canonical_person_id(ctx, system="fhir:id", value=subject_patient_id) if subject_patient_id else _canonical_person_id(ctx)
        event_time = _fhir_event_time(res)

        base = {
            "canonical_person_id": person,
            "source": "fhir",
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
            observations.append(base)
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
            documents.append(base)
        elif rt == "MedicationRequest":
            status = res.get("status")
            if isinstance(status, str):
                base["status"] = status
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            meds.append(base)
        elif rt == "Condition":
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
            base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            conds.append(base)

    return observations, documents, meds, conds


def _export_cda_observations(ctx: ExportContext) -> list[dict]:
    if not ctx.export_cda_rel:
        return []
    path = ctx.root_dir / ctx.export_cda_rel
    if not path.exists():
        return []

    observations: list[dict] = []
    for _, el in ET.iterparse(path, events=("end",)):
        if _localname(el.tag) != "observation":
            continue

        effective_time = None
        code_code = None
        code_display = None
        value_val = None
        value_unit = None

        for child in list(el):
            ln = _localname(child.tag)
            if ln == "effectiveTime":
                v = child.attrib.get("value")
                if isinstance(v, str):
                    effective_time = _normalize_time(v)
            elif ln == "code":
                code_code = child.attrib.get("code")
                code_display = child.attrib.get("displayName")
            elif ln == "value":
                value_val = child.attrib.get("value")
                value_unit = child.attrib.get("unit")

        base = {
            "canonical_person_id": _canonical_person_id(ctx),
            "source": "cda",
            "source_file": _safe_relpath(ctx.export_cda_rel),
            "event_time": effective_time,
            "run_id": ctx.run_id,
            "code": code_code,
            "value": value_val,
            "unit": value_unit,
        }
        base["event_key"] = _sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        observations.append(base)
        el.clear()

    return observations


def export_ndjson(*, input_dir: str, out_dir: str, mode: str = "local") -> None:
    ctx = _resolve_context(input_dir=Path(input_dir), mode=mode)

    healthkit_obs = _export_healthkit_observations(ctx)
    fhir_obs, fhir_docs, fhir_meds, fhir_conds = _export_fhir_streams(ctx)
    cda_obs = _export_cda_observations(ctx)

    observations = [*healthkit_obs, *fhir_obs, *cda_obs]
    documents = [*fhir_docs]
    meds = [*fhir_meds]
    conds = [*fhir_conds]

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

    observations = sort_rows(dedupe(observations))
    documents = sort_rows(dedupe(documents))
    meds = sort_rows(dedupe(meds))
    conds = sort_rows(dedupe(conds))

    _write_ndjson(out_root / "observations.ndjson", observations)
    _write_ndjson(out_root / "documents.ndjson", documents)
    if meds:
        _write_ndjson(out_root / "medications.ndjson", meds)
    if conds:
        _write_ndjson(out_root / "conditions.ndjson", conds)
