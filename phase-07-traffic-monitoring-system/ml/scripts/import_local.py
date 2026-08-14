"""Import a local YOLO dataset, image directory, or exported ZIP into immutable raw storage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from ml.scripts.dataset_registry import DATASET_TYPES, import_local_source
except ModuleNotFoundError:
    from dataset_registry import DATASET_TYPES, import_local_source


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy a local dataset into traceable SadakDrishti raw storage.")
    parser.add_argument("--input", type=Path, required=True, help="Dataset directory or exported ZIP")
    parser.add_argument("--type", choices=DATASET_TYPES, required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--provider", default="Local")
    parser.add_argument("--license", default="UNKNOWN")
    parser.add_argument("--notes", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    destination, record, inspection = import_local_source(
        args.input, args.type, args.source_name, provider=args.provider,
        license_name=args.license, notes=args.notes,
    )
    print(json.dumps({"destination": str(destination), "source": record, "inspection": inspection}, indent=2, ensure_ascii=False))
    if inspection["status"] == "needs_annotation":
        print("STATUS: needs_annotation — images were imported, but no training-ready labels were found.")
    if record["license"] == "UNKNOWN":
        print("WARNING: license is UNKNOWN; verify rights before training or production use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
