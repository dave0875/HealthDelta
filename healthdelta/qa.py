from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DISCLAIMER = "Information-only response for records navigation; not medical advice."


def _read_rows(ndjson_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(ndjson_dir.glob("*.ndjson"), key=lambda p: p.name):
        stream = path.stem
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            row = dict(obj)
            row["_stream"] = stream
            row["_line"] = line_no
            rows.append(row)
    return rows


def _tokenize(question: str) -> set[str]:
    return {x.lower() for x in re.findall(r"[a-zA-Z0-9]+", question) if x}


def _row_text(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("_stream", "")),
        str(row.get("resource_type", "")),
        str(row.get("hk_type", "")),
        str(row.get("source_file", "")),
    ]
    codings = row.get("code_coding")
    if isinstance(codings, list):
        for coding in codings:
            if isinstance(coding, dict):
                parts.append(str(coding.get("code", "")))
    return " ".join(parts).lower()


def answer_question(*, ndjson_dir: str, question: str, citation_limit: int = 8) -> dict[str, Any]:
    q = (question or "").strip()
    tokens = _tokenize(q)
    rows = _read_rows(Path(ndjson_dir))
    if not tokens:
        return {
            "question": q,
            "answer": "Insufficient evidence to answer: question text is empty.",
            "abstained": True,
            "disclaimer": DISCLAIMER,
            "citations": [],
        }

    scored: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        text = _row_text(row)
        score = sum(1 for token in tokens if token in text)
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda item: (-item[0], str(item[1].get("_stream")), str(item[1].get("record_key"))))

    if not scored:
        return {
            "question": q,
            "answer": "Insufficient evidence to answer from local records; unable to find matching citations.",
            "abstained": True,
            "disclaimer": DISCLAIMER,
            "citations": [],
        }

    top = scored[: max(1, citation_limit)]
    citations: list[dict[str, Any]] = []
    stream_counts: dict[str, int] = {}
    for _, row in top:
        stream = str(row.get("_stream", "unknown"))
        stream_counts[stream] = stream_counts.get(stream, 0) + 1
        citations.append(
            {
                "stream": stream,
                "line": row.get("_line"),
                "record_key": row.get("record_key"),
                "source_file": row.get("source_file"),
                "event_time": row.get("event_time"),
            }
        )

    summary = ", ".join([f"{k}:{stream_counts[k]}" for k in sorted(stream_counts.keys())])
    answer = f"Matched local records for '{q}' with evidence in {summary}."
    return {
        "question": q,
        "answer": answer,
        "abstained": False,
        "disclaimer": DISCLAIMER,
        "citations": citations,
    }
