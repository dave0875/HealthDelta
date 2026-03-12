from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from healthdelta.time_utils import UTC


def _now_utc_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timestamp_slug() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def _jsonable_observation_value(key: str, value: Any) -> Any:
    if value is None:
        return None
    if key in {"event_time", "effective_start", "effective_end"} and isinstance(value, datetime):
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return normalized.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return value


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
        actual_sha: str | None = None
        if expected_sha:
            actual_sha = hashlib.sha256(assembled.read_bytes()).hexdigest()
            if actual_sha != expected_sha:
                raise UploadPlaneError(
                    400,
                    "sha256_mismatch",
                    f"assembled sha256 {actual_sha} does not match expected {expected_sha}",
                )
        if actual_sha is None:
            actual_sha = hashlib.sha256(assembled.read_bytes()).hexdigest()

        short_id = session_id[:6]
        dataset_name = f"dataset_{_timestamp_slug()}_{short_id}"
        dataset_dir = self.datasets_root / dataset_name
        dataset_dir.mkdir(parents=True, exist_ok=False)
        current_dataset_name = self._current_dataset_name()
        if not self._materialize_cumulative_ios_dataset(
            dataset_dir=dataset_dir,
            raw_upload_zip=assembled,
            raw_upload_sha=actual_sha,
            current_dataset_name=current_dataset_name,
        ):
            destination = dataset_dir / "export.zip"
            shutil.move(str(assembled), str(destination))
        elif assembled.exists():
            assembled.unlink()

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

    def _materialize_cumulative_ios_dataset(
        self,
        *,
        dataset_dir: Path,
        raw_upload_zip: Path,
        raw_upload_sha: str,
        current_dataset_name: str | None,
    ) -> bool:
        new_upload = self._read_ios_export_zip(raw_upload_zip)
        if new_upload is None:
            return False
        new_rows = self._dedupe_ios_rows(new_upload["rows"])
        new_source_run = {
            "run_id": new_upload["run_id"],
            "raw_upload_sha256": raw_upload_sha,
        }

        previous_rows: list[dict[str, Any]] = []
        previous_source_runs: list[dict[str, Any]] = []
        if current_dataset_name:
            current_dataset_dir = self.datasets_root / current_dataset_name
            self._copy_raw_uploads_forward(current_dataset_dir=current_dataset_dir, next_dataset_dir=dataset_dir)
            previous_export = current_dataset_dir / "export.zip"
            previous_upload = self._read_ios_export_zip(previous_export)
            if previous_upload is not None:
                previous_rows = previous_upload["rows"]
                previous_source_runs = self._normalize_source_runs(previous_upload["manifest"])
            else:
                bootstrap_source_runs = self._bootstrap_source_runs(
                    current_dataset_dir=current_dataset_dir,
                    current_dataset_name=current_dataset_name,
                )
                merged_source_runs = self._merge_source_runs(bootstrap_source_runs, new_source_run)
                merged_row_count = self._write_cumulative_ios_export_from_bootstrap_analysis(
                    current_dataset_dir=current_dataset_dir,
                    export_zip=dataset_dir / "export.zip",
                    new_rows=new_rows,
                    source_runs=merged_source_runs,
                )
                if merged_row_count is not None:
                    metadata = {
                        "mode": "cumulative_ios_current",
                        "raw_uploads": [path.name for path in sorted((dataset_dir / "raw_uploads").glob("*.zip"))],
                        "source_runs": merged_source_runs,
                        "row_counts": {"observations": merged_row_count},
                    }
                    (dataset_dir / "cumulative_sources.json").write_text(
                        json.dumps(metadata, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    return True

        raw_uploads_dir = dataset_dir / "raw_uploads"
        raw_uploads_dir.mkdir(parents=True, exist_ok=True)
        preserved_raw_zip = raw_uploads_dir / f"{raw_upload_sha}.zip"
        if not preserved_raw_zip.exists():
            shutil.copy2(raw_upload_zip, preserved_raw_zip)

        merged_rows = self._merge_ios_rows(previous_rows, new_rows)
        source_runs = self._merge_source_runs(previous_source_runs, new_source_run)
        self._write_cumulative_ios_export(
            export_zip=dataset_dir / "export.zip",
            rows=merged_rows,
            source_runs=source_runs,
        )
        metadata = {
            "mode": "cumulative_ios_current",
            "raw_uploads": [path.name for path in sorted(raw_uploads_dir.glob("*.zip"))],
            "source_runs": source_runs,
            "row_counts": {"observations": len(merged_rows)},
        }
        (dataset_dir / "cumulative_sources.json").write_text(
            json.dumps(metadata, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return True

    def _bootstrap_source_runs(
        self,
        *,
        current_dataset_dir: Path,
        current_dataset_name: str,
    ) -> list[dict[str, Any]]:
        cumulative_sources = current_dataset_dir / "cumulative_sources.json"
        if cumulative_sources.exists():
            try:
                obj = json.loads(cumulative_sources.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                obj = {}
            if isinstance(obj, dict):
                normalized = self._normalize_source_runs(obj)
                if normalized:
                    return normalized
        return [{"run_id": current_dataset_name, "raw_upload_sha256": ""}]

    def _read_ios_export_zip(self, export_zip: Path) -> dict[str, Any] | None:
        if not export_zip.exists():
            return None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                extract_root = Path(tmp)
                self._safe_extract_zip(export_zip=export_zip, extract_root=extract_root)
                candidates = sorted(
                    {
                        manifest.parent
                        for manifest in extract_root.rglob("manifest.json")
                        if manifest.is_file() and (manifest.parent / "ndjson" / "observations.ndjson").exists()
                    },
                    key=lambda p: p.as_posix(),
                )
                if not candidates:
                    return None
                run_dir = candidates[0]
                manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
                if not isinstance(manifest, dict):
                    return None
                observations_path = run_dir / "ndjson" / "observations.ndjson"
                rows = []
                for line in observations_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    if not isinstance(obj, dict):
                        continue
                    rows.append(obj)
                run_id = manifest.get("run_id")
                if not isinstance(run_id, str) or not run_id:
                    run_id = run_dir.name
                return {
                    "run_id": run_id,
                    "manifest": manifest,
                    "rows": rows,
                }
        except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile, UploadPlaneError):
            return None

    def _copy_raw_uploads_forward(self, *, current_dataset_dir: Path, next_dataset_dir: Path) -> None:
        src = current_dataset_dir / "raw_uploads"
        if not src.exists():
            return
        dst = next_dataset_dir / "raw_uploads"
        dst.mkdir(parents=True, exist_ok=True)
        for raw_zip in sorted(src.glob("*.zip")):
            target = dst / raw_zip.name
            if target.exists():
                continue
            shutil.copy2(raw_zip, target)

    def _dedupe_ios_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen_record_keys: set[str] = set()
        for row in rows:
            normalized = dict(row)
            record_key = self._resolve_record_key(normalized)
            if not record_key or record_key in seen_record_keys:
                continue
            normalized["record_key"] = record_key
            seen_record_keys.add(record_key)
            deduped.append(normalized)
        return deduped

    def _merge_ios_rows(
        self,
        previous_rows: list[dict[str, Any]],
        new_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen_record_keys: set[str] = set()
        for row in previous_rows + new_rows:
            normalized = dict(row)
            record_key = self._resolve_record_key(normalized)
            if not record_key or record_key in seen_record_keys:
                continue
            normalized["record_key"] = record_key
            seen_record_keys.add(record_key)
            merged.append(normalized)
        return merged

    def _write_cumulative_ios_export_from_bootstrap_analysis(
        self,
        *,
        current_dataset_dir: Path,
        export_zip: Path,
        new_rows: list[dict[str, Any]],
        source_runs: list[dict[str, Any]],
    ) -> int | None:
        baseline_db = current_dataset_dir / "analysis" / "duckdb" / "run.duckdb"
        if not baseline_db.exists():
            return None

        try:
            import duckdb
        except ImportError:
            return None

        columns = [
            "schema_version",
            "record_key",
            "canonical_person_id",
            "source",
            "source_system",
            "source_file",
            "event_time",
            "run_id",
            "event_key",
            "source_id",
            "record_id",
            "record_type",
            "observation_id",
            "subject_reference",
            "encounter_id",
            "effective_start",
            "effective_end",
            "sample_type",
            "sample_kind",
            "resource_type",
            "code_system",
            "code",
            "display",
            "value",
            "value_num",
            "value_text",
            "category_value",
            "activity_type",
            "duration_seconds",
            "total_energy_burned_num",
            "total_energy_burned_unit",
            "total_distance_num",
            "total_distance_unit",
            "unit",
            "section_code",
            "section_display",
            "section_title",
            "components_json",
            "code_coding_json",
            "type_coding_json",
            "status",
        ]
        baseline_sql = """
            SELECT
              schema_version,
              record_key,
              canonical_person_id,
              source,
              source_system,
              source_file,
              event_time,
              run_id,
              COALESCE(event_key, record_key) AS event_key,
              source_id,
              record_id,
              record_type,
              observation_id,
              subject_reference,
              encounter_id,
              effective_start,
              effective_end,
              hk_type AS sample_type,
              sample_kind,
              resource_type,
              code_system,
              code,
              display,
              value,
              value_num,
              value_text,
              category_value,
              activity_type,
              duration_seconds,
              total_energy_burned_num,
              total_energy_burned_unit,
              total_distance_num,
              total_distance_unit,
              unit,
              section_code,
              section_display,
              section_title,
              components_json,
              code_coding_json,
              type_coding_json,
              status
            FROM observations
            WHERE COALESCE(record_key, '') <> ''
            ORDER BY COALESCE(event_time, effective_start, effective_end), record_key
        """

        con = duckdb.connect(str(baseline_db), read_only=True)
        try:
            baseline_count_row = con.execute(
                "SELECT COUNT(*) FROM observations WHERE COALESCE(record_key, '') <> ''"
            ).fetchone()
            baseline_row_count = int(baseline_count_row[0] or 0) if baseline_count_row else 0
            existing_record_keys: set[str] = set()
            if new_rows:
                candidate_keys = [row["record_key"] for row in new_rows if isinstance(row.get("record_key"), str)]
                if candidate_keys:
                    placeholders = ",".join(["?"] * len(candidate_keys))
                    existing_record_keys = {
                        str(row[0])
                        for row in con.execute(
                            f"SELECT record_key FROM observations WHERE record_key IN ({placeholders})",
                            candidate_keys,
                        ).fetchall()
                        if row and row[0]
                    }

            with tempfile.TemporaryDirectory() as tmp:
                observations_path = Path(tmp) / "observations.ndjson"
                with observations_path.open("w", encoding="utf-8") as out:
                    cursor = con.execute(baseline_sql)
                    while True:
                        batch = cursor.fetchmany(5000)
                        if not batch:
                            break
                        for values in batch:
                            obj = {
                                key: _jsonable_observation_value(key, value)
                                for key, value in zip(columns, values)
                                if _jsonable_observation_value(key, value) is not None
                            }
                            out.write(json.dumps(obj, sort_keys=True) + "\n")

                    appended_count = 0
                    for row in new_rows:
                        record_key = row["record_key"]
                        if record_key in existing_record_keys:
                            continue
                        out.write(json.dumps(row, sort_keys=True) + "\n")
                        appended_count += 1

                self._write_cumulative_ios_export_from_ndjson(
                    export_zip=export_zip,
                    observations_path=observations_path,
                    row_count=baseline_row_count + appended_count,
                    source_runs=source_runs,
                )
            return baseline_row_count + appended_count
        finally:
            con.close()

    def _resolve_record_key(self, row: dict[str, Any]) -> str:
        for key in ("record_key", "event_key", "source_id"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        payload = json.dumps(row, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _normalize_source_runs(self, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        source_runs = manifest.get("source_runs")
        if isinstance(source_runs, list):
            normalized: list[dict[str, Any]] = []
            for row in source_runs:
                if not isinstance(row, dict):
                    continue
                run_id = row.get("run_id")
                raw_sha = row.get("raw_upload_sha256")
                if isinstance(run_id, str) and run_id and isinstance(raw_sha, str) and raw_sha:
                    normalized.append({"run_id": run_id, "raw_upload_sha256": raw_sha})
            if normalized:
                return normalized
        run_id = manifest.get("run_id")
        if isinstance(run_id, str) and run_id:
            return [{"run_id": run_id, "raw_upload_sha256": ""}]
        return []

    def _merge_source_runs(
        self,
        previous_source_runs: list[dict[str, Any]],
        new_source_run: dict[str, Any],
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for row in previous_source_runs + [new_source_run]:
            run_id = row.get("run_id")
            raw_sha = row.get("raw_upload_sha256")
            if not isinstance(run_id, str) or not run_id:
                continue
            if not isinstance(raw_sha, str):
                raw_sha = ""
            key = (run_id, raw_sha)
            if key in seen:
                continue
            seen.add(key)
            merged.append({"run_id": run_id, "raw_upload_sha256": raw_sha})
        return merged

    def _write_cumulative_ios_export(
        self,
        *,
        export_zip: Path,
        rows: list[dict[str, Any]],
        source_runs: list[dict[str, Any]],
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            observations_path = Path(tmp) / "observations.ndjson"
            with observations_path.open("w", encoding="utf-8") as out:
                for row in rows:
                    out.write(json.dumps(row, sort_keys=True) + "\n")
            self._write_cumulative_ios_export_from_ndjson(
                export_zip=export_zip,
                observations_path=observations_path,
                row_count=len(rows),
                source_runs=source_runs,
            )

    def _write_cumulative_ios_export_from_ndjson(
        self,
        *,
        export_zip: Path,
        observations_path: Path,
        row_count: int,
        source_runs: list[dict[str, Any]],
    ) -> None:
        run_id = "run_orin_cumulative_current"
        observations_bytes = observations_path.read_bytes() if observations_path.exists() else b""
        manifest = {
            "run_id": run_id,
            "files": [
                {
                    "path": "ndjson/observations.ndjson",
                    "size_bytes": len(observations_bytes),
                    "sha256": hashlib.sha256(observations_bytes).hexdigest(),
                }
            ],
            "row_counts": {"observations": row_count},
            "source_runs": source_runs,
        }
        with zipfile.ZipFile(export_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"{run_id}/manifest.json", json.dumps(manifest, sort_keys=True))
            archive.write(observations_path, arcname=f"{run_id}/ndjson/observations.ndjson")

    def _safe_extract_zip(self, *, export_zip: Path, extract_root: Path) -> None:
        extract_root.mkdir(parents=True, exist_ok=True)
        resolved_root = extract_root.resolve()
        with zipfile.ZipFile(export_zip, "r") as archive:
            for member in archive.infolist():
                rel = Path(member.filename)
                target = (extract_root / rel).resolve()
                if target != resolved_root and resolved_root not in target.parents:
                    raise UploadPlaneError(400, "invalid_upload_archive", f"unsafe zip member path: {member.filename}")
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member, "r") as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
