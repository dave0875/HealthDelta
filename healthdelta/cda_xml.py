from __future__ import annotations

import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from xml.etree import ElementTree as ET

from healthdelta.progress import progress


RESUBMIT_EMAIL = "dave0875@gmail.com"
_ROOT_CLOSE = b"</ClinicalDocument>"


class CdaRepairError(RuntimeError):
    pass


@dataclass(frozen=True)
class CdaRepairSummary:
    was_repaired: bool
    premature_root_closes_removed: int
    final_root_closes_appended: int


@dataclass(frozen=True)
class ParsedCda:
    sections: list[dict[str, object]]
    observations: list[dict[str, object]]
    encounters: list[dict[str, object]]


def _localname(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _xml_child_attr(el: ET.Element, child_name: str, attr_name: str) -> str | None:
    for child in list(el):
        if _localname(child.tag) != child_name:
            continue
        raw = child.attrib.get(attr_name)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _xml_child_text(el: ET.Element, child_name: str) -> str | None:
    for child in list(el):
        if _localname(child.tag) != child_name:
            continue
        raw = "".join(child.itertext()).strip()
        return raw or None
    return None


def _normalize_time(raw: str | None) -> str | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    if not value:
        return None
    digits = value
    tz = "Z"
    if value.endswith("Z"):
        digits = value[:-1]
    elif len(value) >= 5 and value[-5] in {"+", "-"} and value[-4:].isdigit():
        tz = value[-5:-2] + ":" + value[-2:]
        digits = value[:-5]
    if len(digits) >= 14 and digits[:14].isdigit():
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}T{digits[8:10]}:{digits[10:12]}:{digits[12:14]}{tz}"
    if len(digits) >= 8 and digits[:8].isdigit():
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}T00:00:00{tz}"
    return None


def repair_cda_xml(*, src: Path, dst: Path) -> CdaRepairSummary:
    dst.parent.mkdir(parents=True, exist_ok=True)
    saw_root_open = False
    saw_root_close = False
    pending_root_close: bytes | None = None
    pending_ws: list[bytes] = []
    premature_root_closes_removed = 0
    final_root_closes_appended = 0
    task = progress.task("repair export_cda.xml", total=src.stat().st_size, unit="bytes")

    with src.open("rb") as fsrc, dst.open("wb") as fdst:
        for raw_line in fsrc:
            task.advance(len(raw_line))
            stripped = raw_line.strip()
            if not saw_root_open and b"<ClinicalDocument" in raw_line and not stripped.startswith(b"</"):
                saw_root_open = True

            if pending_root_close is not None:
                if not stripped:
                    pending_ws.append(raw_line)
                    continue
                premature_root_closes_removed += 1
                pending_root_close = None
                for ws_line in pending_ws:
                    fdst.write(ws_line)
                pending_ws.clear()

            if stripped == _ROOT_CLOSE:
                saw_root_close = True
                pending_root_close = raw_line
                pending_ws = []
                continue

            fdst.write(raw_line)

        if pending_root_close is not None:
            fdst.write(pending_root_close)
            for ws_line in pending_ws:
                fdst.write(ws_line)
        elif saw_root_open and saw_root_close:
            fdst.write(_ROOT_CLOSE + b"\n")
            final_root_closes_appended = 1
        elif saw_root_open and not saw_root_close:
            raise CdaRepairError(
                "export_cda.xml appears truncated and cannot be safely repaired; "
                f"please resubmit the file and notify {RESUBMIT_EMAIL}"
            )

    return CdaRepairSummary(
        was_repaired=bool(premature_root_closes_removed or final_root_closes_appended),
        premature_root_closes_removed=premature_root_closes_removed,
        final_root_closes_appended=final_root_closes_appended,
    )


@contextmanager
def repaired_cda_path(src: Path) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="healthdelta_cda_") as td:
        repaired = Path(td) / "export_cda.xml"
        repair_cda_xml(src=src, dst=repaired)
        yield repaired


def iter_cda_content(path: Path) -> Iterator[tuple[str, dict[str, object]]]:
    task = progress.task("parse export_cda.xml", unit="elements")
    for _event, el in ET.iterparse(str(path), events=("end",)):
        ln = _localname(el.tag)
        if ln == "section":
            section_code = _xml_child_attr(el, "code", "code")
            section_display = _xml_child_attr(el, "code", "displayName")
            section_title = _xml_child_text(el, "title")
            section_time = _normalize_time(_xml_child_attr(el, "effectiveTime", "value"))
            if section_code or section_display or section_title:
                yield (
                    "section",
                    {
                        "section_code": section_code,
                        "section_display": section_display,
                        "section_title": section_title,
                        "event_time": section_time,
                    },
                )
            for observation in [child for child in el.iter() if _localname(child.tag) == "observation"]:
                yield (
                    "observation",
                    {
                        "section_code": section_code,
                        "section_display": section_display,
                        "section_title": section_title,
                        "event_time": _normalize_time(_xml_child_attr(observation, "effectiveTime", "value")),
                        "code": _xml_child_attr(observation, "code", "code"),
                        "code_display": _xml_child_attr(observation, "code", "displayName"),
                        "value": _xml_child_attr(observation, "value", "value"),
                        "unit": _xml_child_attr(observation, "value", "unit"),
                    },
                )
            el.clear()
            task.advance(1)
        elif ln in {"encompassingEncounter", "serviceEvent"}:
            start = None
            end = None
            for child in list(el):
                if _localname(child.tag) != "effectiveTime":
                    continue
                direct = child.attrib.get("value")
                if isinstance(direct, str) and direct.strip():
                    start = _normalize_time(direct)
                    end = start
                    break
                for grand in list(child):
                    raw = grand.attrib.get("value")
                    if not isinstance(raw, str):
                        continue
                    if _localname(grand.tag) == "low":
                        start = _normalize_time(raw)
                    elif _localname(grand.tag) == "high":
                        end = _normalize_time(raw)
            event_time = start or end
            if event_time:
                yield ("encounter", {"event_time": event_time, "start_time": start, "end_time": end})
            el.clear()
            task.advance(1)


def parse_cda_xml(path: Path) -> ParsedCda:
    sections: list[dict[str, object]] = []
    observations: list[dict[str, object]] = []
    encounters: list[dict[str, object]] = []
    for kind, row in iter_cda_content(path):
        if kind == "section":
            sections.append(row)
        elif kind == "observation":
            observations.append(row)
        elif kind == "encounter":
            encounters.append(row)
    return ParsedCda(sections=sections, observations=observations, encounters=encounters)
