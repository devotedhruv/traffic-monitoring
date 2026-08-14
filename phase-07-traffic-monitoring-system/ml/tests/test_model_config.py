from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from config import settings
from ml.scripts.common import EXPECTED_CLASSES, MODEL_TYPES, dataset_config_path, load_dataset_config
from services.plate_detector import PlateDetector
from services.plate_ocr import PlateAggregator, ocr_dependency_status
from web.violations import HelmetSpecialist


class ModelConfigurationTests(unittest.TestCase):
    def test_missing_tesseract_is_reported_without_startup_failure(self):
        status = ocr_dependency_status("tesseract", command="definitely-not-installed-tesseract", languages="nep+eng")
        self.assertFalse(status["available"])
        self.assertFalse(status["executable"])
        self.assertEqual(status["languages"], [])

    def test_bundled_dataset_yamls_have_exact_training_class_order(self):
        for model_type in MODEL_TYPES:
            with self.subTest(model_type=model_type):
                config = load_dataset_config(dataset_config_path(model_type))
                self.assertEqual(config.names, EXPECTED_CLASSES[model_type])
                self.assertEqual(set(config.splits), {"train", "val", "test"})
                for split, path in config.splits.items():
                    self.assertEqual(path, config.root / "images" / split)

    def test_missing_custom_vehicle_model_uses_empty_optional_override(self):
        self.assertEqual(settings._optional_existing_model("ml/models/vehicle/missing.pt", "vehicle"), "")
        self.assertTrue(Path(settings.MODEL_PATH).is_file())
        self.assertTrue(Path(settings.LIVE_MODEL_PATH).is_file())

    def test_missing_specialist_models_disable_only_the_specialist(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing = str(Path(temporary) / "missing.pt")
            self.assertFalse(PlateDetector(missing).available)
            helmet = HelmetSpecialist(missing, 0.4)
            self.assertFalse(helmet.available)
            self.assertIn("not configured", helmet.reason.lower())

    def test_plate_voting_uses_repetition_recency_and_crop_quality(self):
        aggregator = PlateAggregator(minimum_confirmed_observations=2)
        aggregator.add(37, "BA 2 CHA 1234", 0.91, 10.0, crop_quality=0.95)
        aggregator.add(37, "BA 2 WA 1234", 0.60, 10.1, crop_quality=0.15)
        result = aggregator.add(37, "BA-2-CHA-1234", 0.88, 10.2, crop_quality=0.90)
        self.assertEqual(result.status, "CONFIRMED")
        self.assertEqual(result.text, "BA 2 CHA 1234")
        self.assertGreater(result.confidence, 0.78)


if __name__ == "__main__":
    unittest.main()
