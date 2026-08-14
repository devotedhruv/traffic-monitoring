"""Register and safely select validated SadakDrishti production weights."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from ml.scripts.common import MODEL_ROOT, MODEL_TYPES, REPOSITORY_ROOT, promote_model
except ModuleNotFoundError:
    from common import MODEL_ROOT, MODEL_TYPES, REPOSITORY_ROOT, promote_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy/version validated weights and update a portable environment configuration.",
    )
    parser.add_argument("--type", choices=MODEL_TYPES, required=True)
    parser.add_argument("--model", type=Path, required=True, help="Validated .pt weights")
    parser.add_argument("--env-file", type=Path, default=REPOSITORY_ROOT / ".env", help="Runtime env file to update")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        from ultralytics import YOLO
        YOLO(str(args.model.expanduser().resolve()))
    except ImportError as exc:
        raise SystemExit("Ultralytics is required to verify that production weights are readable") from exc
    except Exception as exc:
        raise SystemExit(f"Model readability check failed ({type(exc).__name__}); promotion was not applied") from exc
    result = promote_model(args.type, args.model, args.env_file, MODEL_ROOT)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("Promotion gates passed. Review the environment-file change, then restart SadakDrishti.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
