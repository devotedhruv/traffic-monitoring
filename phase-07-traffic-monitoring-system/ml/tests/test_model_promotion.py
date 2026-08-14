from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ml.scripts.common import REPOSITORY_ROOT, promote_model, register_model


class ModelPromotionTests(unittest.TestCase):
    def test_unevaluated_registered_model_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary); weights = root / "best.pt"; weights.write_bytes(b"weights")
            registry = root / "registry"
            record = register_model("plate", weights, {"datasetVersion": "plate-v1"}, registry)
            with self.assertRaisesRegex(ValueError, "measured precision"):
                promote_model("plate", REPOSITORY_ROOT / record["modelPath"], root / ".env", registry)


if __name__ == "__main__":
    unittest.main()
