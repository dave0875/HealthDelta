from __future__ import annotations

import json

from healthdelta.cda_xml import iter_cda_content, repaired_cda_path
from healthdelta import ndjson_export as _base


def _export_cda_streams(ctx: _base.ExportContext) -> tuple[list[dict], list[dict]]:
    if not ctx.export_cda_rel:
        return [], []
    path = ctx.root_dir / ctx.export_cda_rel
    if not path.exists():
        return [], []

    observations: list[dict] = []
    encounters: list[dict] = []

    with repaired_cda_path(path) as repaired_cda:
        for kind, row in iter_cda_content(repaired_cda):
            if kind == "section":
                base = {
                    "schema_version": 2,
                    "canonical_person_id": _base._canonical_person_id(ctx),
                    "source": "cda",
                    "source_system": _base._source_system_tag("cda:export_cda.xml"),
                    "source_file": _base._safe_relpath(ctx.export_cda_rel),
                    "event_time": row.get("event_time"),
                    "run_id": ctx.run_id,
                    "resource_type": "CDASection",
                    "section_code": row.get("section_code"),
                    "section_display": row.get("section_display"),
                    "section_title": row.get("section_title"),
                }
                base["event_key"] = _base._sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
                base["record_key"] = base["event_key"]
                observations.append(base)
            elif kind == "observation":
                base = {
                    "schema_version": 2,
                    "canonical_person_id": _base._canonical_person_id(ctx),
                    "source": "cda",
                    "source_system": _base._source_system_tag("cda:export_cda.xml"),
                    "source_file": _base._safe_relpath(ctx.export_cda_rel),
                    "event_time": row.get("event_time"),
                    "run_id": ctx.run_id,
                    "resource_type": "CDAObservation",
                    "section_code": row.get("section_code"),
                    "section_display": row.get("section_display"),
                    "section_title": row.get("section_title"),
                    "code": row.get("code"),
                    "value": row.get("value"),
                    "unit": row.get("unit"),
                }
                base["event_key"] = _base._sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
                base["record_key"] = base["event_key"]
                observations.append(base)
            elif kind == "encounter":
                base = {
                    "schema_version": 2,
                    "canonical_person_id": _base._canonical_person_id(ctx),
                    "source": "cda",
                    "source_system": _base._source_system_tag("cda:export_cda.xml"),
                    "source_file": _base._safe_relpath(ctx.export_cda_rel),
                    "event_time": row.get("event_time"),
                    "run_id": ctx.run_id,
                    "resource_type": "CDAEncounter",
                    "start_time": row.get("start_time"),
                    "end_time": row.get("end_time"),
                }
                base["event_key"] = _base._sha256_bytes(json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8"))
                base["record_key"] = base["event_key"]
                encounters.append(base)

    return observations, encounters


def export_ndjson(*, input_dir: str, out_dir: str, mode: str = "local") -> None:
    original = _base._export_cda_streams
    _base._export_cda_streams = _export_cda_streams
    try:
        return _base.export_ndjson(input_dir=input_dir, out_dir=out_dir, mode=mode)
    finally:
        _base._export_cda_streams = original
