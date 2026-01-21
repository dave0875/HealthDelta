from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


BASE_REQUIRED_KEYS: tuple[str, ...] = ("canonical_person_id", "source", "source_file", "event_time", "run_id")


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

    for path in files:
        rel = path.relative_to(root).as_posix()
        data = path.read_bytes()
        if data and not data.endswith(b"\n"):
            errors.append(ValidationError(rel_path=rel, line_no=0, code="missing_trailing_newline", message="file must be newline-terminated"))

        with path.open("r", encoding="utf-8") as f:
            for line_no, raw in enumerate(f, start=1):
                line = raw.rstrip("\n")
                if line.endswith("\r"):
                    line = line[:-1]
                if not line.strip():
                    errors.append(ValidationError(rel_path=rel, line_no=line_no, code="empty_line", message="blank lines are not allowed"))
                    continue

                for token in banned_tokens:
                    if token in line:
                        errors.append(
                            ValidationError(rel_path=rel, line_no=line_no, code="banned_token", message=f"found banned token: {token!r}")
                        )
                for pat in banned_res:
                    if pat.search(line):
                        errors.append(
                            ValidationError(rel_path=rel, line_no=line_no, code="banned_pattern", message=f"matched banned pattern: {pat.pattern!r}")
                        )

                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    errors.append(ValidationError(rel_path=rel, line_no=line_no, code="invalid_json", message=str(e)))
                    continue

                if not isinstance(obj, dict):
                    errors.append(
                        ValidationError(rel_path=rel, line_no=line_no, code="not_object", message=f"expected JSON object, got {type(obj).__name__}")
                    )
                    continue

                for k in BASE_REQUIRED_KEYS:
                    if k not in obj:
                        errors.append(
                            ValidationError(rel_path=rel, line_no=line_no, code="missing_required_key", message=f"missing required key: {k}")
                        )
                        continue
                    if not isinstance(obj[k], str):
                        errors.append(
                            ValidationError(
                                rel_path=rel,
                                line_no=line_no,
                                code="invalid_type",
                                message=f"key {k} must be a string",
                            )
                        )

    return sorted(errors, key=lambda e: (e.rel_path, e.line_no, e.code, e.message))

