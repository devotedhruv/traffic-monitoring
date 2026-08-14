from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
import yaml

from ml.scripts.dataset_merge import merge_sources
from ml.scripts.split_dataset import assign_groups, load_groups


class DatasetSplitTests(unittest.TestCase):
    def test_group_priority_and_legacy_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "frames.jsonl"
            manifest.write_text("\n".join([
                json.dumps({"image": "one.jpg", "source_video": "a.mp4", "session_id": "s", "camera_id": "c"}),
                json.dumps({"image": "two.jpg", "session": "legacy-session"}),
            ]) + "\n", encoding="utf-8")
            groups = load_groups(manifest)
            self.assertEqual(groups["one.jpg"]["group"], "source_video:a.mp4")
            self.assertEqual(groups["two.jpg"]["group"], "session_id:legacy-session")

    def test_assignment_is_deterministic_and_group_atomic(self):
        groups = {f"video-{index}": [Path(f"{index}-{item}.jpg") for item in range(index + 1)] for index in range(8)}
        first = assign_groups(groups, 42, (0.7, 0.2, 0.1))
        second = assign_groups(groups, 42, (0.7, 0.2, 0.1))
        self.assertEqual(first, second)
        self.assertEqual(set(first), set(groups))

    def test_versioned_merge_preserves_source_and_canonical_labels(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = []
            for source_index in range(2):
                source = root / f"plate-source-{source_index}"
                for split_index, split in enumerate(("train", "val", "test")):
                    (source / "images" / split).mkdir(parents=True)
                    (source / "labels" / split).mkdir(parents=True)
                    frame = np.full((20, 30, 3), 20 + source_index * 20 + split_index, np.uint8)
                    cv2.imwrite(str(source / "images" / split / f"frame-{split}.jpg"), frame)
                    (source / "labels" / split / f"frame-{split}.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
                (source / "data.yaml").write_text(yaml.safe_dump({
                    "path": ".", "train": "images/train", "val": "images/val", "test": "images/test",
                    "names": {0: "license_plate"},
                }), encoding="utf-8")
                sources.append(str(source))
            output = root / "plate-v1"
            metadata = merge_sources("plate", sources, "plate-v1", output)
            self.assertEqual(metadata["train_images"], 2)
            self.assertEqual(metadata["sources"], ["plate-source-0", "plate-source-1"])
            self.assertEqual(len((output / "provenance.jsonl").read_text(encoding="utf-8").splitlines()), 6)


if __name__ == "__main__":
    unittest.main()
