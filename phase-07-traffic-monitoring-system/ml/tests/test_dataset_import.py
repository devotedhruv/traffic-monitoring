from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

import cv2
import numpy as np

from ml.scripts.dataset_registry import import_local_source, read_sources
from ml.scripts.normalize_dataset import normalize


class DatasetImportTests(unittest.TestCase):
    def test_images_only_import_is_traceable_and_needs_annotation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            cv2.imwrite(str(source / "frame.jpg"), np.zeros((12, 16, 3), np.uint8))
            destination, record, inspection = import_local_source(
                source, "plate", "own-nepal-plate", metadata_root=root / "metadata", raw_root=root / "raw",
            )
            self.assertTrue((destination / "frame.jpg").is_file())
            self.assertEqual(inspection["status"], "needs_annotation")
            self.assertEqual(record["license"], "UNKNOWN")
            self.assertEqual(read_sources(root / "metadata")[0]["source_id"], "own-nepal-plate")

    def test_duplicate_source_id_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"; source.mkdir()
            cv2.imwrite(str(source / "frame.jpg"), np.zeros((8, 8, 3), np.uint8))
            kwargs = {"metadata_root": root / "metadata", "raw_root": root / "raw"}
            import_local_source(source, "vehicle", "source-one", **kwargs)
            with self.assertRaises(FileExistsError):
                import_local_source(source, "vehicle", "source-one", **kwargs)

    def test_normalization_rewrites_frame_manifest_to_new_filename(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / "source"; source.mkdir()
            cv2.imwrite(str(source / "frame.jpg"), np.zeros((8, 8, 3), np.uint8))
            (source / "frames.jsonl").write_text(json.dumps({
                "image": "frame.jpg", "source_video": "video.mp4", "session_id": "session-1",
            }) + "\n", encoding="utf-8")
            report = normalize(source, root / "normalized", "source-one")
            record = json.loads((root / "normalized" / "frames.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(report["frame_metadata_records"], 1)
            self.assertEqual(record["image"], "source-one__frame.jpg")
            self.assertEqual(record["session_id"], "session-1")


if __name__ == "__main__":
    unittest.main()
