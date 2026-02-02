from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from healthdelta.upload_plane import UploadPlane


class TestUploadPlane(unittest.TestCase):
    def test_session_bookkeeping_and_finalize(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plane = UploadPlane(Path(tmp))
            payload = b"abc123xyz"
            sha = hashlib.sha256(payload).hexdigest()
            session = plane.create_session(total_size=len(payload), sha256=sha)
            sid = session["id"]

            plane.put_chunk(sid, 0, b"abc")
            plane.put_chunk(sid, 1, b"123xyz")
            status = plane.get_session(sid)
            self.assertEqual(status["received_chunks"], [0, 1])
            self.assertEqual(status["received_bytes"], len(payload))

            finalized = plane.finalize_session(sid)
            dataset = finalized["finalized_dataset"]
            self.assertIsNotNone(dataset)

            current = plane.get_current_dataset()
            self.assertEqual(current["dataset"], dataset)
            export_zip = Path(current["export_zip"])
            self.assertTrue(export_zip.exists())
            self.assertEqual(export_zip.read_bytes(), payload)

    def test_archive_current_clears_pointer_and_lists_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plane = UploadPlane(Path(tmp))
            session = plane.create_session(total_size=4, sha256=hashlib.sha256(b"data").hexdigest())
            sid = session["id"]
            plane.put_chunk(sid, 0, b"data")
            plane.finalize_session(sid)

            archived = plane.archive_current()
            self.assertIn("archive_", archived["archive"])
            archives = plane.list_archives()
            self.assertEqual(len(archives), 1)
            self.assertTrue(archives[0]["has_export_zip"])


if __name__ == "__main__":
    unittest.main()
