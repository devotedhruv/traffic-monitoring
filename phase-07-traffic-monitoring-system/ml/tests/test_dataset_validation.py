from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
import yaml

from ml.scripts.common import load_dataset_config, parse_annotation_file, validate_dataset


class DatasetValidationTests(unittest.TestCase):
    def test_valid_dataset_counts_annotations_and_empty_negative(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vehicles"
            for index, split in enumerate(("train", "val", "test")):
                (root / "images" / split).mkdir(parents=True)
                (root / "labels" / split).mkdir(parents=True)
                cv2.imwrite(str(root / "images" / split / f"{split}.jpg"), np.full((40, 60, 3), 120 + index, np.uint8))
                (root / "labels" / split / f"{split}.txt").write_text(
                    "2 0.5 0.5 0.4 0.4\n" if split != "test" else "", encoding="utf-8"
                )
            yaml_path = Path(temporary) / "vehicle.yaml"
            yaml_path.write_text(yaml.safe_dump({
                "path": str(root), "train": "images/train", "val": "images/val",
                "test": "images/test", "names": {0: "person", 1: "bicycle", 2: "car"},
            }), encoding="utf-8")
            report = validate_dataset(load_dataset_config(yaml_path))
            self.assertEqual(report.errors, 0)
            self.assertEqual(report.images, 3)
            self.assertEqual(report.annotations, 2)
            self.assertEqual(report.empty_images, 1)

    def test_invalid_annotations_report_class_range_coordinates_duplicates_and_zero_size(self):
        with tempfile.TemporaryDirectory() as temporary:
            label = Path(temporary) / "bad.txt"
            label.write_text(
                "4 0.5 0.5 0.2 0.2\n"
                "0 1.2 0.5 0.2 0.2\n"
                "0 0.5 0.5 0 0\n"
                "0 0.5 0.5 0.2 0.2\n"
                "0 0.5 0.5 0.2 0.2\n"
                "not yolo\n",
                encoding="utf-8",
            )
            annotations, issues = parse_annotation_file(label, {0, 1})
            codes = {issue.code for issue in issues}
            self.assertEqual(len(annotations), 1)
            self.assertTrue({
                "invalid_class_id", "coordinate_out_of_range", "zero_width", "zero_height",
                "duplicate_annotation", "invalid_field_count",
            }.issubset(codes))

    def test_missing_label_and_orphan_label_are_critical(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "plates"
            for split in ("train", "val", "test"):
                (root / "images" / split).mkdir(parents=True)
                (root / "labels" / split).mkdir(parents=True)
            cv2.imwrite(str(root / "images" / "train" / "missing.jpg"), np.zeros((10, 10, 3), np.uint8))
            (root / "labels" / "val" / "orphan.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
            yaml_path = Path(temporary) / "plate.yaml"
            yaml_path.write_text(yaml.safe_dump({
                "path": str(root), "train": "images/train", "val": "images/val",
                "test": "images/test", "names": {0: "license_plate"},
            }), encoding="utf-8")
            report = validate_dataset(load_dataset_config(yaml_path))
            codes = {issue.code for issue in report.issues}
            self.assertIn("missing_label", codes)
            self.assertIn("missing_image", codes)
            self.assertGreaterEqual(report.errors, 2)

    def test_empty_splits_are_critical(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "helmets"
            for split in ("train", "val", "test"):
                (root / "images" / split).mkdir(parents=True)
                (root / "labels" / split).mkdir(parents=True)
            yaml_path = Path(temporary) / "helmet.yaml"
            yaml_path.write_text(yaml.safe_dump({
                "path": str(root), "train": "images/train", "val": "images/val",
                "test": "images/test", "names": {0: "helmet", 1: "no_helmet"},
            }), encoding="utf-8")
            report = validate_dataset(load_dataset_config(yaml_path), check_images=False)
            self.assertEqual(report.errors, 3)
            self.assertEqual({issue.code for issue in report.issues}, {"empty_split"})

    def test_duplicate_image_across_splits_is_critical(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "plates"
            frame = np.full((20, 30, 3), 42, np.uint8)
            for split in ("train", "val", "test"):
                (root / "images" / split).mkdir(parents=True)
                (root / "labels" / split).mkdir(parents=True)
                cv2.imwrite(str(root / "images" / split / f"{split}.png"), frame)
                (root / "labels" / split / f"{split}.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
            yaml_path = Path(temporary) / "plate.yaml"
            yaml_path.write_text(yaml.safe_dump({
                "path": str(root), "train": "images/train", "val": "images/val",
                "test": "images/test", "names": {0: "license_plate"},
            }), encoding="utf-8")
            report = validate_dataset(load_dataset_config(yaml_path), check_images=False)
            self.assertIn("duplicate_image_across_splits", {issue.code for issue in report.issues})


if __name__ == "__main__":
    unittest.main()
