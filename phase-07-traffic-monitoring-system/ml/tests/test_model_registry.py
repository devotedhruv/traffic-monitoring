from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ml.scripts.common import REPOSITORY_ROOT, register_model


class ModelRegistryTests(unittest.TestCase):
    def test_registration_writes_registry_and_version_sidecar(self):
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary); weights = root / "best.pt"; weights.write_bytes(b"weights")
            registry = root / "registry"
            record = register_model("plate", weights, {
                "version": "plate-v7", "datasetVersion": "plate-v4",
                "precision": .8, "recall": .9, "mAP50": .91, "mAP50_95": .6,
                "evaluationDataset": "fixed-test.yaml", "evaluationSplit": "test",
                "evaluatedAt": "2026-08-13T00:00:00Z",
            }, registry)
            self.assertEqual(record["version"], "plate-v7")
            self.assertTrue((registry / "plate" / "plate-v7.json").is_file())


if __name__ == "__main__":
    unittest.main()

