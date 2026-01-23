from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from healthdelta.progress import progress


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


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _system_fingerprint(system: str) -> str:
    return _sha256_text(system.strip())


def _source_patient_id_fingerprint(system: str, value: str) -> str:
    return _sha256_text(f"{system.strip()}:{value.strip()}")


def _person_link_id(system_fingerprint: str, source_patient_id: str) -> str:
    return _sha256_text(f"{system_fingerprint}:{source_patient_id}")


@dataclass(frozen=True)
class _PatientHit:
    rel: str
    idx: int
    parsed: ParsedName
    external_ids: list[dict]


def _load_person_links(identity_dir: Path) -> dict:
    path = identity_dir / "person_links.json"
    if not path.exists():
        return {"schema_version": 1, "run_id": None, "links": []}
    obj = _read_json(path)
    if isinstance(obj, dict) and isinstance(obj.get("links"), list):
        return obj
    raise ValueError(f"Invalid person_links.json: {path}")


def review_identity_links(*, identity_dir: str = "data/identity") -> list[str]:
    """
    Returns deterministic, share-safe lines for unverified links.
    Output lines intentionally avoid names/DOBs and include only fingerprints + person_key.
    """
    root = Path(identity_dir)
    obj = _load_person_links(root)
    links = obj.get("links")
    if not isinstance(links, list):
        return []

    rows: list[tuple[str, str]] = []
    for link in links:
        if not isinstance(link, dict):
            continue
        if link.get("verification_state") != "unverified":
            continue
        sys_fp = link.get("system_fingerprint")
        src_pid = link.get("source_patient_id")
        person_key = link.get("person_key")
        if not (isinstance(sys_fp, str) and isinstance(src_pid, str) and isinstance(person_key, str)):
            continue
        link_id = _person_link_id(sys_fp, src_pid)
        rows.append((link_id, person_key))

    return [f"{link_id} person_key={person_key}" for link_id, person_key in sorted(rows, key=lambda r: r[0])]


def confirm_identity_link(*, identity_dir: str = "data/identity", link_id: str) -> bool:
    """
    Marks the identified link as user_confirmed.
    Returns True if the link exists (even if already confirmed), False if not found.
    """
    root = Path(identity_dir)
    obj = _load_person_links(root)
    links = obj.get("links")
    if not isinstance(links, list):
        raise ValueError("person_links.json missing links")

    found = False
    updated_any = False
    updated_links: list[dict] = []
    for link in links:
        if not isinstance(link, dict):
            continue
        sys_fp = link.get("system_fingerprint")
        src_pid = link.get("source_patient_id")
        if not (isinstance(sys_fp, str) and isinstance(src_pid, str)):
            continue
        lid = _person_link_id(sys_fp, src_pid)
        if lid != link_id:
            updated_links.append(link)
            continue

        found = True
        if link.get("verification_state") != "user_confirmed":
            link = {**link, "verification_state": "user_confirmed"}
            updated_any = True
        updated_links.append(link)

    if not found:
        return False

    if updated_any:
        # Preserve existing metadata, but normalize the links ordering deterministically.
        obj_out = dict(obj)
        obj_out["links"] = sorted(
            updated_links,
            key=lambda l: (l.get("system_fingerprint", ""), l.get("source_patient_id", ""), l.get("person_key", "")),
        )
        _write_json(root / "person_links.json", obj_out)
    return True


def build_identity(*, staging_run_dir: str, output_dir: str = "data/identity") -> None:
    with progress.phase("identity: init"):
        run_dir = Path(staging_run_dir)
        layout_path = run_dir / "layout.json"
        if not layout_path.exists():
            raise FileNotFoundError("Missing layout.json in staging run dir")

    with progress.phase("identity: load layout"):
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
    links_path = identity_dir / "person_links.json"

    people: list[dict] = []
    aliases: list[dict] = []
    links: list[dict] = []
    with progress.phase("identity: load existing state"):
        if people_path.exists():
            obj = _read_json(people_path)
            if isinstance(obj, dict) and isinstance(obj.get("people"), list):
                people = obj["people"]
        if aliases_path.exists():
            obj = _read_json(aliases_path)
            if isinstance(obj, dict) and isinstance(obj.get("aliases"), list):
                aliases = obj["aliases"]
        if links_path.exists():
            obj = _read_json(links_path)
            if isinstance(obj, dict) and isinstance(obj.get("links"), list):
                links = obj["links"]

    name_to_people: dict[tuple[str, str], list[str]] = {}
    for person in people:
        if not isinstance(person, dict):
            continue
        first_norm = person.get("first_norm")
        last_norm = person.get("last_norm")
        person_key = person.get("person_key")
        if isinstance(first_norm, str) and isinstance(last_norm, str) and isinstance(person_key, str):
            name_to_people.setdefault((first_norm, last_norm), [])
            if person_key not in name_to_people[(first_norm, last_norm)]:
                name_to_people[(first_norm, last_norm)].append(person_key)

    alias_keys_existing = set()
    for alias in aliases:
        if isinstance(alias, dict) and isinstance(alias.get("alias_key"), str):
            alias_keys_existing.add(alias["alias_key"])

    link_key_to_person: dict[tuple[str, str], str] = {}
    for link in links:
        if not isinstance(link, dict):
            continue
        sys_fp = link.get("system_fingerprint")
        src_pid = link.get("source_patient_id")
        person_key = link.get("person_key")
        state = link.get("verification_state")
        if not (isinstance(sys_fp, str) and isinstance(src_pid, str) and isinstance(person_key, str)):
            continue
        if state not in {"verified", "unverified", "user_confirmed"}:
            continue
        link_key_to_person[(sys_fp, src_pid)] = person_key

    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    # First pass: collect all Patient resources and count name collisions within this run.
    hits: list[_PatientHit] = []
    with progress.phase("identity: scan clinical JSON"):
        task = progress.task("identity: scan clinical JSON", total=len(clinical_paths), unit="files")
        for rel in clinical_paths:
            if not isinstance(rel, str):
                task.advance(1)
                continue
            p = run_dir / rel
            if not p.exists():
                task.advance(1)
                continue
            try:
                content = _read_json(p)
            except json.JSONDecodeError:
                task.advance(1)
                continue

            resources = _walk_fhir_resources(content)
            for idx, res in enumerate(resources):
                if res.get("resourceType") != "Patient":
                    continue
                name = _extract_patient_name(res)
                if not name:
                    continue
                try:
                    parsed = parse_name(name)
                except ValueError:
                    continue

                external_ids = _extract_external_ids(res)
                hits.append(_PatientHit(rel=rel, idx=idx, parsed=parsed, external_ids=external_ids))
            task.advance(1)

    name_counts: dict[tuple[str, str], int] = {}
    for h in hits:
        k = (h.parsed.first_norm, h.parsed.last_norm)
        name_counts[k] = name_counts.get(k, 0) + 1

    def _create_person(*, parsed: ParsedName) -> str:
        person_key = str(uuid.uuid4())
        people.append(
            {
                "person_key": person_key,
                "first_norm": parsed.first_norm,
                "last_norm": parsed.last_norm,
                "created_at": now,
            }
        )
        name_to_people.setdefault((parsed.first_norm, parsed.last_norm), [])
        name_to_people[(parsed.first_norm, parsed.last_norm)].append(person_key)
        return person_key

    def _add_links(*, person_key: str, external_ids: list[dict], verification_state: str) -> None:
        if verification_state not in {"verified", "unverified", "user_confirmed"}:
            raise ValueError(f"Invalid verification_state: {verification_state}")
        for ext in external_ids:
            if not isinstance(ext, dict):
                continue
            system = ext.get("system")
            value = ext.get("value")
            if not (isinstance(system, str) and isinstance(value, str) and system.strip() and value.strip()):
                continue

            sys_fp = _system_fingerprint(system)
            src_pid = _source_patient_id_fingerprint(system, value)
            key = (sys_fp, src_pid)
            existing = link_key_to_person.get(key)
            if existing is not None:
                if existing != person_key:
                    raise RuntimeError(f"Conflicting PersonLink for {key}: {existing} vs {person_key}")
                continue
            link_key_to_person[key] = person_key
            links.append(
                {
                    "system_fingerprint": sys_fp,
                    "source_patient_id": src_pid,
                    "person_key": person_key,
                    "verification_state": verification_state,
                }
            )

    # Second pass: assign person_key and append aliases + links.
    with progress.phase("identity: assign people + aliases"):
        task = progress.task("identity: assign people", total=len(hits), unit="records")
        batch = 0
        for h in sorted(hits, key=lambda x: (x.rel, x.idx)):
            try:
                match_key = (h.parsed.first_norm, h.parsed.last_norm)

                linked_person_keys = set()
                for ext in h.external_ids:
                    if not isinstance(ext, dict):
                        continue
                    system = ext.get("system")
                    value = ext.get("value")
                    if not (isinstance(system, str) and isinstance(value, str) and system.strip() and value.strip()):
                        continue
                    key = (_system_fingerprint(system), _source_patient_id_fingerprint(system, value))
                    pk = link_key_to_person.get(key)
                    if isinstance(pk, str) and pk:
                        linked_person_keys.add(pk)

                if len(linked_person_keys) > 1:
                    raise RuntimeError(f"Patient has external IDs linked to multiple people: {sorted(linked_person_keys)}")

                person_key: str | None = next(iter(linked_person_keys)) if linked_person_keys else None
                link_state_for_new = "unverified"

                if person_key is None:
                    candidates = name_to_people.get(match_key, [])
                    if name_counts.get(match_key, 0) == 1 and len(candidates) == 1:
                        # Unambiguous name match: link to existing person, but keep unverified until confirmed.
                        person_key = candidates[0]
                    else:
                        # Ambiguous within the run or multiple candidates exist: do not auto-merge.
                        person_key = _create_person(parsed=h.parsed)

                    _add_links(person_key=person_key, external_ids=h.external_ids, verification_state=link_state_for_new)

                alias_payload: dict[str, Any] = {
                    "person_key": person_key,
                    "first_raw": h.parsed.first,
                    "last_raw": h.parsed.last,
                    "first_norm": h.parsed.first_norm,
                    "last_norm": h.parsed.last_norm,
                    "name_raw": h.parsed.raw,
                    "source": {
                        "run_id": run_id,
                        "file": h.rel,
                        "external_ids": h.external_ids,
                    },
                }
                alias_key = _stable_alias_key(alias_payload)
                if alias_key in alias_keys_existing:
                    continue
                alias_keys_existing.add(alias_key)
                aliases.append({**alias_payload, "alias_key": alias_key, "observed_at": now})
            finally:
                batch += 1
                if batch >= 200:
                    task.advance(batch)
                    batch = 0
        if batch:
            task.advance(batch)

    people_out = {
        "schema_version": 1,
        "run_id": run_id,
        "people": sorted(people, key=lambda p: (p.get("last_norm", ""), p.get("first_norm", ""), p.get("person_key", ""))),
        "notes": {
            "matching_rule": "same person iff first_norm AND last_norm match",
            "normalization": "trim + collapse whitespace + casefold; middle names/initials ignored by taking first token and last token",
        },
    }
    aliases_out = {
        "schema_version": 1,
        "run_id": run_id,
        "aliases": sorted(aliases, key=lambda a: (a.get("last_norm", ""), a.get("first_norm", ""), a.get("alias_key", ""))),
        "notes": {
            "append_only": True,
            "dedupe_rule": "alias_key = sha256(stable alias payload)",
        },
    }
    links_out = {
        "schema_version": 1,
        "run_id": run_id,
        "links": sorted(links, key=lambda l: (l.get("system_fingerprint", ""), l.get("source_patient_id", ""), l.get("person_key", ""))),
        "notes": {
            "identifiers": "system_fingerprint and source_patient_id are sha256 fingerprints; raw external IDs are not stored here",
            "verification_state": ["verified", "unverified", "user_confirmed"],
        },
    }

    with progress.phase("identity: write outputs"):
        task = progress.task("identity: write outputs", total=3, unit="files")
        _write_json(people_path, people_out)
        task.advance(1)
        _write_json(aliases_path, aliases_out)
        task.advance(1)
        _write_json(links_path, links_out)
        task.advance(1)
