from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from healthdelta.progress import progress


BASE_REQUIRED_KEYS: tuple[str, ...] = ("canonical_person_id", "source", "source_file", "event_time", "run_id", "record_key")
SCHEMA_ROOT = Path(__file__).resolve().parent.parent / "schemas" / "ndjson"


@dataclass(frozen=True)
class ValidationError:
    rel_path: str
    line_no: int
    code: str
    message: str

    def format(self) -> str:
        return f"{self.rel_path}:{self.line_no} {self.code} {self.message}"


def _iter_ndjson_files(root: Path) -> list[Path]:
    files = [p for p in root.rglob("*.ndjson") if p.is_file()]
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def _stream_name(rel_path: str) -> str:
    return Path(rel_path).stem


def _validate_by_schema(
    *,
    rel_path: str,
    line_no: int,
    obj: dict,
    schema_cache: dict[tuple[str, int], dict | None],
) -> list[ValidationError]:
    errs: list[ValidationError] = []
    stream = _stream_name(rel_path)
    schema_version = obj.get("schema_version")
    if not isinstance(schema_version, int):
        return errs

    key = (stream, schema_version)
    schema = schema_cache.get(key)
    if key not in schema_cache:
        schema_path = SCHEMA_ROOT / f"v{schema_version}" / f"{stream}.schema.json"
        if schema_path.exists():
            try:
                loaded = json.loads(schema_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                loaded = None
            schema_cache[key] = loaded if isinstance(loaded, dict) else None
        else:
            schema_cache[key] = None
    schema = schema_cache.get(key)

    if schema is None:
        errs.append(
            ValidationError(
                rel_path=rel_path,
                line_no=line_no,
                code="schema_version_incompatible",
                message=f"no schema for stream={stream!r} schema_version={schema_version}",
            )
        )
        return errs

    required = schema.get("required")
    if isinstance(required, list):
        for k in required:
            if isinstance(k, str) and k not in obj:
                errs.append(
                    ValidationError(rel_path=rel_path, line_no=line_no, code="missing_required_key", message=f"missing required key: {k}")
                )

    properties = schema.get("properties")
    if isinstance(properties, dict):
        for k, spec in properties.items():
            if k not in obj or not isinstance(spec, dict):
                continue
            t = spec.get("type")
            if t == "string" and not isinstance(obj[k], str):
                errs.append(ValidationError(rel_path=rel_path, line_no=line_no, code="invalid_type", message=f"key {k} must be a string"))
            if t == "integer" and not isinstance(obj[k], int):
                errs.append(ValidationError(rel_path=rel_path, line_no=line_no, code="invalid_type", message=f"key {k} must be an integer"))
    return errs


def _clinical_required_keys(rel_path: str, obj: dict) -> tuple[str, ...]:
    stream = _stream_name(rel_path)
    resource_type = obj.get("resource_type")
    if not isinstance(resource_type, str) or not resource_type.strip():
        return ()

    if stream == "observations" and resource_type == "Observation":
        return ("record_id", "record_type", "observation_id", "subject_reference", "code_system")
    if stream == "observations" and resource_type == "Immunization":
        return ("source_id", "resource_type", "status")
    if stream == "medications" and resource_type in {"MedicationRequest", "MedicationStatement", "MedicationDispense"}:
        return ("record_id", "record_type", "subject_reference", "source_id")
    if stream == "conditions" and resource_type in {"Condition", "AllergyIntolerance"}:
        return ("record_id", "record_type", "subject_reference", "source_id")
    if stream == "encounters" and resource_type == "Encounter":
        return ("record_id", "record_type", "encounter_id", "subject_reference")
    if stream == "procedures" and resource_type == "Procedure":
        return ("record_id", "record_type", "subject_reference", "source_id")
    return ()


def _validate_clinical_rulepack(*, rel_path: str, line_no: int, obj: dict) -> list[ValidationError]:
    errs: list[ValidationError] = []
    for key in _clinical_required_keys(rel_path, obj):
        value = obj.get(key)
        if not isinstance(value, str) or not value.strip():
            errs.append(
                ValidationError(
                    rel_path=rel_path,
                    line_no=line_no,
                    code="clinical_required_key_missing",
                    message=f"missing clinical required key: {key}",
                )
            )
    return errs


def validate_ndjson_dir(
    *,
    input_dir: str,
    banned_tokens: list[str] | None = None,
    banned_regexes: list[str] | None = None,
) -> list[ValidationError]:
    root = Path(input_dir)
    banned_tokens = [t for t in (banned_tokens or []) if t]
    banned_regexes = [r for r in (banned_regexes or []) if r]
    banned_res = [re.compile(p) for p in banned_regexes]

    files = _iter_ndjson_files(root)
    if not files:
        return [ValidationError(rel_path=".", line_no=0, code="no_ndjson_files", message="no *.ndjson files found under input_dir")]

    errors: list[ValidationError] = []
    schema_cache: dict[tuple[str, int], dict | None] = {}

    with progress.phase("validate: ndjson"):
        task_files = progress.task("validate: files", total=len(files), unit="files")

        for path in files:
            rel = path.relative_to(root).as_posix()

            data = path.read_bytes()
            if data and not data.endswith(b"\n"):
                errors.append(ValidationError(rel_path=rel, line_no=0, code="missing_trailing_newline", message="file must be newline-terminated"))

            task_lines = progress.task("validate: scan lines", unit="lines")
            batch = 0
            with path.open("r", encoding="utf-8") as f:
                for line_no, raw in enumerate(f, start=1):
                    line = raw.rstrip("\n")
                    if line.endswith("\r"):
                        line = line[:-1]
                    if not line.strip():
                        errors.append(ValidationError(rel_path=rel, line_no=line_no, code="empty_line", message="blank lines are not allowed"))
                        batch += 1
                        if batch >= 5000:
                            task_lines.advance(batch)
                            batch = 0
                        continue

                    for token in banned_tokens:
                        if token in line:
                            errors.append(ValidationError(rel_path=rel, line_no=line_no, code="banned_token", message=f"found banned token: {token!r}"))
                    for pat in banned_res:
                        if pat.search(line):
                            errors.append(
                                ValidationError(rel_path=rel, line_no=line_no, code="banned_pattern", message=f"matched banned pattern: {pat.pattern!r}")
                            )

                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError as e:
                        errors.append(ValidationError(rel_path=rel, line_no=line_no, code="invalid_json", message=str(e)))
                        batch += 1
                        if batch >= 5000:
                            task_lines.advance(batch)
                            batch = 0
                        continue

                    if not isinstance(obj, dict):
                        errors.append(
                            ValidationError(rel_path=rel, line_no=line_no, code="not_object", message=f"expected JSON object, got {type(obj).__name__}")
                        )
                        batch += 1
                        if batch >= 5000:
                            task_lines.advance(batch)
                            batch = 0
                        continue

                    for k in BASE_REQUIRED_KEYS:
                        if k not in obj:
                            errors.append(
                                ValidationError(rel_path=rel, line_no=line_no, code="missing_required_key", message=f"missing required key: {k}")
                            )
                            continue
                        if not isinstance(obj[k], str):
                            errors.append(
                                ValidationError(rel_path=rel, line_no=line_no, code="invalid_type", message=f"key {k} must be a string")
                            )

                    if "schema_version" not in obj:
                        errors.append(
                            ValidationError(rel_path=rel, line_no=line_no, code="missing_required_key", message="missing required key: schema_version")
                        )
                    elif not isinstance(obj.get("schema_version"), int):
                        errors.append(
                            ValidationError(rel_path=rel, line_no=line_no, code="invalid_type", message="key schema_version must be an integer")
                        )
                    else:
                        errors.extend(
                            _validate_by_schema(rel_path=rel, line_no=line_no, obj=obj, schema_cache=schema_cache)
                        )
                        errors.extend(_validate_clinical_rulepack(rel_path=rel, line_no=line_no, obj=obj))

                    batch += 1
                    if batch >= 5000:
                        task_lines.advance(batch)
                        batch = 0

            if batch:
                task_lines.advance(batch)

            task_files.advance(1)

    return sorted(errors, key=lambda e: (e.rel_path, e.line_no, e.code, e.message))
