from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from healthdelta.time_utils import UTC


def _now_utc_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timestamp_slug() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


@dataclass
class UploadPlaneError(Exception):
    status: int
    code: str
    detail: str


class UploadPlane:
    """File-system-backed upload sessions + dataset pointer management."""

    def __init__(self, data_root: Path):
        self.data_root = Path(data_root)
        self.uploads_root = self.data_root / "uploads"
        self.datasets_root = self.data_root / "datasets"
        self.archives_root = self.data_root / "archives"
        self.current_symlink = self.datasets_root / "current"
        self.current_fallback = self.datasets_root / "current.txt"
        self.ensure_layout()

    def ensure_layout(self) -> None:
        for p in (self.data_root, self.uploads_root, self.datasets_root, self.archives_root):
            p.mkdir(parents=True, exist_ok=True)

    def create_session(self, *, total_size: int, sha256: str | None = None) -> dict[str, Any]:
        if total_size <= 0:
            raise UploadPlaneError(400, "invalid_total_size", "total_size must be a positive integer")
        if sha256 is not None:
            normalized = sha256.strip().lower()
            if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
                raise UploadPlaneError(400, "invalid_sha256", "sha256 must be a 64-character hex string")
            sha256 = normalized

        session_id = uuid.uuid4().hex[:12]
        session_dir = self._session_dir(session_id)
        chunks_dir = session_dir / "chunks"
        chunks_dir.mkdir(parents=True, exist_ok=False)
        obj: dict[str, Any] = {
            "id": session_id,
            "status": "created",
            "created_at": _now_utc_iso(),
            "updated_at": _now_utc_iso(),
            "total_size": int(total_size),
            "sha256": sha256,
            "received_chunks": [],
            "received_bytes": 0,
            "finalized_dataset": None,
        }
        self._write_session_json(session_id, obj)
        return obj

    def get_session(self, session_id: str) -> dict[str, Any]:
        obj = self._read_session_json(session_id)
        chunk_indexes = self._received_chunk_indexes(session_id)
        obj["received_chunks"] = chunk_indexes
        obj["received_bytes"] = self._total_chunk_bytes(session_id, chunk_indexes)
        return obj

    def put_chunk(self, session_id: str, index: int, content: bytes) -> dict[str, Any]:
        if index < 0:
            raise UploadPlaneError(400, "invalid_chunk_index", "chunk index must be >= 0")
        if len(content) == 0:
            raise UploadPlaneError(400, "invalid_chunk", "chunk body cannot be empty")

        obj = self._read_session_json(session_id)
        if obj.get("status") == "finalized":
            raise UploadPlaneError(409, "session_finalized", "cannot upload chunks after finalize")

        chunk_path = self._chunk_path(session_id, index)
        chunk_path.parent.mkdir(parents=True, exist_ok=True)
        chunk_path.write_bytes(content)

        indexes = self._received_chunk_indexes(session_id)
        obj["received_chunks"] = indexes
        obj["received_bytes"] = self._total_chunk_bytes(session_id, indexes)
        obj["status"] = "uploading"
        obj["updated_at"] = _now_utc_iso()
        self._write_session_json(session_id, obj)
        return obj

    def finalize_session(self, session_id: str) -> dict[str, Any]:
        obj = self._read_session_json(session_id)
        if obj.get("status") == "finalized":
            return obj

        indexes = self._received_chunk_indexes(session_id)
        if not indexes:
            raise UploadPlaneError(400, "missing_chunks", "no chunks uploaded")
        expected = list(range(0, indexes[-1] + 1))
        if indexes != expected:
            raise UploadPlaneError(
                400,
                "missing_chunks",
                f"chunk indexes must be contiguous from 0..{indexes[-1]}; got {indexes}",
            )

        assembled = self._session_dir(session_id) / "export.zip"
        with assembled.open("wb") as out:
            for idx in indexes:
                out.write(self._chunk_path(session_id, idx).read_bytes())

        assembled_size = assembled.stat().st_size
        expected_size = int(obj.get("total_size") or 0)
        if assembled_size != expected_size:
            raise UploadPlaneError(
                400,
                "size_mismatch",
                f"assembled size {assembled_size} does not match expected total_size {expected_size}",
            )

        expected_sha = obj.get("sha256")
        if expected_sha:
            actual_sha = hashlib.sha256(assembled.read_bytes()).hexdigest()
            if actual_sha != expected_sha:
                raise UploadPlaneError(
                    400,
                    "sha256_mismatch",
                    f"assembled sha256 {actual_sha} does not match expected {expected_sha}",
                )

        short_id = session_id[:6]
        dataset_name = f"dataset_{_timestamp_slug()}_{short_id}"
        dataset_dir = self.datasets_root / dataset_name
        dataset_dir.mkdir(parents=True, exist_ok=False)
        destination = dataset_dir / "export.zip"
        shutil.move(str(assembled), str(destination))

        self._set_current_dataset(dataset_name)
        obj["status"] = "finalized"
        obj["finalized_dataset"] = dataset_name
        obj["updated_at"] = _now_utc_iso()
        obj["received_chunks"] = indexes
        obj["received_bytes"] = expected_size
        self._write_session_json(session_id, obj)
        return obj

    def get_current_dataset(self) -> dict[str, Any]:
        name = self._current_dataset_name()
        if not name:
            raise UploadPlaneError(404, "no_current_dataset", "no current dataset is set")
        dataset_dir = self.datasets_root / name
        export_zip = dataset_dir / "export.zip"
        if not export_zip.exists():
            raise UploadPlaneError(
                500,
                "current_dataset_missing",
                f"current dataset '{name}' is missing export.zip at {export_zip}",
            )
        return {
            "dataset": name,
            "path": str(dataset_dir),
            "export_zip": str(export_zip),
            "size_bytes": export_zip.stat().st_size,
            "updated_at": _now_utc_iso(),
        }

    def archive_current(self) -> dict[str, Any]:
        name = self._current_dataset_name()
        if not name:
            raise UploadPlaneError(404, "no_current_dataset", "no current dataset is set")
        src = self.datasets_root / name
        if not src.exists():
            raise UploadPlaneError(500, "current_dataset_missing", f"current dataset dir does not exist: {src}")
        archive_name = f"archive_{_timestamp_slug()}_{name}"
        dst = self.archives_root / archive_name
        shutil.move(str(src), str(dst))
        self._clear_current_dataset()
        return {
            "archived_dataset": name,
            "archive": archive_name,
            "path": str(dst),
            "updated_at": _now_utc_iso(),
        }

    def list_archives(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in sorted(self.archives_root.iterdir()):
            if not p.is_dir():
                continue
            export_zip = p / "export.zip"
            out.append(
                {
                    "archive": p.name,
                    "path": str(p),
                    "has_export_zip": export_zip.exists(),
                    "size_bytes": export_zip.stat().st_size if export_zip.exists() else 0,
                }
            )
        return out

    def _session_dir(self, session_id: str) -> Path:
        if not session_id or "/" in session_id or ".." in session_id:
            raise UploadPlaneError(400, "invalid_session_id", "session id is invalid")
        return self.uploads_root / f"session_{session_id}"

    def _session_json_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "session.json"

    def _chunk_path(self, session_id: str, index: int) -> Path:
        return self._session_dir(session_id) / "chunks" / f"{index:06d}"

    def _read_session_json(self, session_id: str) -> dict[str, Any]:
        path = self._session_json_path(session_id)
        if not path.exists():
            raise UploadPlaneError(404, "session_not_found", f"upload session '{session_id}' was not found")
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise UploadPlaneError(500, "session_corrupt", f"session metadata is unreadable: {exc}") from exc
        if not isinstance(obj, dict):
            raise UploadPlaneError(500, "session_corrupt", "session metadata JSON is not an object")
        return obj

    def _write_session_json(self, session_id: str, obj: dict[str, Any]) -> None:
        path = self._session_json_path(session_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    def _received_chunk_indexes(self, session_id: str) -> list[int]:
        chunks_dir = self._session_dir(session_id) / "chunks"
        if not chunks_dir.exists():
            return []
        indexes: list[int] = []
        for p in chunks_dir.iterdir():
            if not p.is_file():
                continue
            try:
                indexes.append(int(p.name))
            except ValueError:
                continue
        return sorted(indexes)

    def _total_chunk_bytes(self, session_id: str, indexes: list[int]) -> int:
        total = 0
        for idx in indexes:
            total += self._chunk_path(session_id, idx).stat().st_size
        return total

    def _set_current_dataset(self, dataset_name: str) -> None:
        self._clear_current_dataset()
        target = self.datasets_root / dataset_name
        if not target.exists():
            raise UploadPlaneError(500, "dataset_missing", f"dataset path does not exist: {target}")
        try:
            self.current_symlink.symlink_to(dataset_name)
        except OSError:
            self.current_fallback.write_text(dataset_name + "\n", encoding="utf-8")

    def _clear_current_dataset(self) -> None:
        if self.current_symlink.exists() or self.current_symlink.is_symlink():
            self.current_symlink.unlink()
        if self.current_fallback.exists():
            self.current_fallback.unlink()

    def _current_dataset_name(self) -> str | None:
        if self.current_symlink.is_symlink():
            target = self.current_symlink.readlink()
            return target.name
        if self.current_fallback.exists():
            name = self.current_fallback.read_text(encoding="utf-8").strip()
            return name or None
        return None
