from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ml.scripts.common import (
    REPOSITORY_ROOT, next_model_version, promote_model, read_registry, register_model,
    update_env_file,
)


class TrainingUtilityTests(unittest.TestCase):
    def test_registry_versions_and_metadata_are_reproducible(self):
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            registry_root = root / "registry"
            source = root / "best.pt"
            source.write_bytes(b"test weights")
            record = register_model("plate", source, {
                "baseModel": "yolo11s.pt", "datasetVersion": "plates-v1", "epochs": 150,
                "imageSize": 960, "precision": 0.9, "recall": 0.8,
                "mAP50": 0.91, "mAP50_95": 0.62, "notes": "unit test",
            }, registry_root=registry_root)
            self.assertEqual(record["version"], "plate-v1")
            self.assertTrue((registry_root / "plate" / "plate-v1.pt").is_file())
            registry = read_registry("plate", registry_root)
            self.assertEqual(next_model_version(registry, "plate"), "plate-v2")
            self.assertEqual(registry["models"][0]["datasetVersion"], "plates-v1")
            self.assertIn("gitCommit", registry["models"][0])

    def test_environment_update_preserves_unrelated_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_file = Path(temporary) / ".env"
            env_file.write_text("KEEP_ME=yes\nTRAFFIC_PLATE_MODEL_PATH=old.pt\n", encoding="utf-8")
            update_env_file(env_file, {"TRAFFIC_PLATE_MODEL_PATH": "ml/models/plate/plate-v1.pt"})
            content = env_file.read_text(encoding="utf-8")
            self.assertIn("KEEP_ME=yes", content)
            self.assertIn("TRAFFIC_PLATE_MODEL_PATH=ml/models/plate/plate-v1.pt", content)
            self.assertNotIn("old.pt", content)

    def test_promotion_uses_repository_relative_paths_and_updates_registry(self):
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            registry_root = root / "registry"
            source = root / "best.pt"
            source.write_bytes(b"test weights")
            record = register_model("helmet", source, {
                "datasetVersion": "helmet-v1", "precision": 0.8, "recall": 0.81,
                "mAP50": 0.84, "mAP50_95": 0.55,
                "evaluationDataset": "ml/datasets/versions/helmet/helmet-v1/data.yaml",
                "evaluationSplit": "test", "evaluatedAt": "2026-08-13T00:00:00Z",
            }, registry_root)
            model = REPOSITORY_ROOT / record["modelPath"]
            env_file = root / ".env"
            result = promote_model("helmet", model, env_file, registry_root)
            self.assertFalse(Path(result["modelPath"]).is_absolute())
            self.assertEqual(result["productionVersion"], "helmet-v1")
            self.assertIn("TRAFFIC_HELMET_MODEL_PATH=", env_file.read_text(encoding="utf-8"))
            metadata = json.loads((registry_root / "helmet" / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["productionVersion"], "helmet-v1")
            self.assertEqual(metadata["promotionHistory"][0]["previousVersion"], None)

    def test_promotion_rejects_external_absolute_model_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            model = Path(temporary) / "plate-v9.pt"
            model.write_bytes(b"weights")
            with self.assertRaises(ValueError):
                promote_model("plate", model, Path(temporary) / ".env")


if __name__ == "__main__":
    unittest.main()
