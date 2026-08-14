from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
import yaml

from ml.scripts.class_mapping import default_mapping
from ml.scripts.remap_classes import remap


class ClassMappingTests(unittest.TestCase):
    def test_questionable_vehicle_classes_are_not_implicitly_mapped(self):
        mapping = default_mapping("vehicle", ["Motorbike", "Pedestrian", "Van", "Rickshaw", "Auto"])
        self.assertEqual(mapping["Motorbike"], "motorcycle")
        self.assertEqual(mapping["Pedestrian"], "person")
        self.assertIsNone(mapping["Van"])
        self.assertIsNone(mapping["Rickshaw"])
        self.assertIsNone(mapping["Auto"])

    def test_remap_rewrites_ids_and_drops_null_class(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / "source"; output = root / "output"
            (source / "images").mkdir(parents=True); (source / "labels").mkdir()
            cv2.imwrite(str(source / "images" / "rider.jpg"), np.zeros((20, 20, 3), np.uint8))
            (source / "labels" / "rider.txt").write_text("1 0.5 0.5 0.2 0.2\n2 0.5 0.5 0.1 0.1\n", encoding="utf-8")
            (source / "data.yaml").write_text(yaml.safe_dump({"names": {0: "With Helmet", 1: "Without Helmet", 2: "Licence"}}), encoding="utf-8")
            mapping = root / "mapping.json"
            mapping.write_text(json.dumps({"With Helmet": "helmet", "Without Helmet": "no_helmet", "Licence": None}), encoding="utf-8")
            report = remap(source, output, "helmet", mapping)
            self.assertEqual((output / "labels" / "rider.txt").read_text(encoding="utf-8").split()[0], "1")
            self.assertEqual(report["ignored_annotations"], 1)


if __name__ == "__main__":
    unittest.main()

