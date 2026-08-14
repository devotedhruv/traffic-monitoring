"""Register a traceable dataset source without downloading or modifying it."""

from __future__ import annotations

import argparse
import json

try:
    from ml.scripts.dataset_registry import DATASET_TYPES, register_source
except ModuleNotFoundError:
    from dataset_registry import DATASET_TYPES, register_source


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add or update SadakDrishti dataset provenance metadata.")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--type", choices=DATASET_TYPES, required=True)
    parser.add_argument("--source-identifier", default="")
    parser.add_argument("--license", default="UNKNOWN")
    parser.add_argument("--notes", default="")
    parser.add_argument("--replace", action="store_true", help="Replace an existing record with the same source ID")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    record = register_source({
        "source_id": args.source_id, "name": args.name, "provider": args.provider,
        "dataset_type": args.type, "source_identifier": args.source_identifier,
        "license": args.license, "notes": args.notes,
    }, replace=args.replace)
    print(json.dumps(record, indent=2, ensure_ascii=False))
    if record["license"] == "UNKNOWN":
        print("WARNING: license is UNKNOWN; verify usage rights before training or commercial deployment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

