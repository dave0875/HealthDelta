from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedName:
    raw: str
    first: str
    last: str
    first_norm: str
    last_norm: str


_WHITESPACE_RE = re.compile(r"\s+")


def _collapse_ws(s: str) -> str:
    return _WHITESPACE_RE.sub(" ", s.strip())


def normalize_name_token(token: str) -> str:
    return _collapse_ws(token).casefold()


def parse_name(name: str) -> ParsedName:
    raw = name
    s = _collapse_ws(name)
    if not s:
        raise ValueError("Empty name")

    if "," in s:
        left, right = s.split(",", 1)
        last = _collapse_ws(left)
        right = _collapse_ws(right)
        first = right.split(" ", 1)[0] if right else ""
    else:
        tokens = s.split(" ")
        first = tokens[0]
        last = tokens[-1] if len(tokens) > 1 else ""

    first = _collapse_ws(first)
    last = _collapse_ws(last)
    if not first or not last:
        raise ValueError(f"Name must include first and last: {raw!r}")

    return ParsedName(
        raw=raw,
        first=first,
        last=last,
        first_norm=normalize_name_token(first),
        last_norm=normalize_name_token(last),
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _stable_alias_key(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _extract_patient_name(patient: dict) -> str | None:
    names = patient.get("name")
    if isinstance(names, list) and names:
        first = names[0]
        if isinstance(first, dict):
            text = first.get("text")
            if isinstance(text, str) and text.strip():
                return text
            family = first.get("family")
            given = first.get("given")
            if isinstance(family, str) and isinstance(given, list) and given and isinstance(given[0], str):
                return f"{given[0]} {family}"
    text = patient.get("text")
    if isinstance(text, dict):
        div = text.get("div")
        if isinstance(div, str) and div.strip():
            return div
    return None


def _extract_external_ids(patient: dict) -> list[dict]:
    external: list[dict] = []
    pid = patient.get("id")
    if isinstance(pid, str) and pid.strip():
        external.append({"system": "fhir:id", "value": pid})

    identifiers = patient.get("identifier")
    if isinstance(identifiers, list):
        for ident in identifiers:
            if not isinstance(ident, dict):
                continue
            system = ident.get("system")
            value = ident.get("value")
            if isinstance(system, str) and isinstance(value, str) and system.strip() and value.strip():
                external.append({"system": system, "value": value})

    deduped: list[dict] = []
    seen = set()
    for item in external:
        key = (item["system"], item["value"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _walk_fhir_resources(obj: object) -> list[dict]:
    resources: list[dict] = []
    if isinstance(obj, dict):
        rt = obj.get("resourceType")
        if isinstance(rt, str):
            resources.append(obj)
        for v in obj.values():
            resources.extend(_walk_fhir_resources(v))
    elif isinstance(obj, list):
        for v in obj:
            resources.extend(_walk_fhir_resources(v))
    return resources


def build_identity(*, staging_run_dir: str, output_dir: str = "data/identity") -> None:
    run_dir = Path(staging_run_dir)
    layout_path = run_dir / "layout.json"
    if not layout_path.exists():
        raise FileNotFoundError(f"Missing layout.json in staging run dir: {run_dir}")

    layout = _read_json(layout_path)
    run_id = layout.get("run_id") if isinstance(layout.get("run_id"), str) else run_dir.name

    clinical_paths = layout.get("clinical_json")
    if clinical_paths is None:
        raise ValueError("layout.json missing clinical_json")
    if not isinstance(clinical_paths, list):
        raise ValueError("layout.json clinical_json must be a list")

    identity_dir = Path(output_dir)
    people_path = identity_dir / "people.json"
    aliases_path = identity_dir / "aliases.json"

    people: list[dict] = []
    aliases: list[dict] = []
    if people_path.exists():
        obj = _read_json(people_path)
        if isinstance(obj, dict) and isinstance(obj.get("people"), list):
            people = obj["people"]
    if aliases_path.exists():
        obj = _read_json(aliases_path)
        if isinstance(obj, dict) and isinstance(obj.get("aliases"), list):
            aliases = obj["aliases"]

    key_to_person: dict[tuple[str, str], str] = {}
    for person in people:
        if not isinstance(person, dict):
            continue
        first_norm = person.get("first_norm")
        last_norm = person.get("last_norm")
        person_key = person.get("person_key")
        if isinstance(first_norm, str) and isinstance(last_norm, str) and isinstance(person_key, str):
            key_to_person[(first_norm, last_norm)] = person_key

    alias_keys_existing = set()
    for alias in aliases:
        if isinstance(alias, dict) and isinstance(alias.get("alias_key"), str):
            alias_keys_existing.add(alias["alias_key"])

    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    for rel in clinical_paths:
        if not isinstance(rel, str):
            continue
        p = run_dir / rel
        if not p.exists():
            continue
        try:
            content = _read_json(p)
        except json.JSONDecodeError:
            continue

        resources = _walk_fhir_resources(content)
        for res in resources:
            if res.get("resourceType") != "Patient":
                continue
            name = _extract_patient_name(res)
            if not name:
                continue
            try:
                parsed = parse_name(name)
            except ValueError:
                continue

            match_key = (parsed.first_norm, parsed.last_norm)
            person_key = key_to_person.get(match_key)
            if person_key is None:
                person_key = str(uuid.uuid4())
                key_to_person[match_key] = person_key
                people.append(
                    {
                        "person_key": person_key,
                        "first_norm": parsed.first_norm,
                        "last_norm": parsed.last_norm,
                        "created_at": now,
                    }
                )

            external_ids = _extract_external_ids(res)
            alias_payload = {
                "person_key": person_key,
                "first_raw": parsed.first,
                "last_raw": parsed.last,
                "first_norm": parsed.first_norm,
                "last_norm": parsed.last_norm,
                "name_raw": parsed.raw,
                "source": {
                    "run_id": run_id,
                    "file": rel,
                    "external_ids": external_ids,
                },
            }
            alias_key = _stable_alias_key(alias_payload)
            if alias_key in alias_keys_existing:
                continue
            alias_keys_existing.add(alias_key)
            aliases.append({**alias_payload, "alias_key": alias_key, "observed_at": now})

    people_out = {
        "people": sorted(people, key=lambda p: (p.get("last_norm", ""), p.get("first_norm", ""), p.get("person_key", ""))),
        "notes": {
            "matching_rule": "same person iff first_norm AND last_norm match",
            "normalization": "trim + collapse whitespace + casefold; middle names/initials ignored by taking first token and last token",
        },
    }
    aliases_out = {
        "aliases": sorted(aliases, key=lambda a: (a.get("last_norm", ""), a.get("first_norm", ""), a.get("alias_key", ""))),
        "notes": {
            "append_only": True,
            "dedupe_rule": "alias_key = sha256(stable alias payload)",
        },
    }

    _write_json(people_path, people_out)
    _write_json(aliases_path, aliases_out)
