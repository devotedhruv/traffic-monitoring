"""Small high-level dispatcher for modular SadakDrishti dataset tools."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    from ml.scripts.common import DATASET_ROOT, DATASET_TO_MODEL, EXPECTED_CLASSES
    from ml.scripts.dataset_merge import merge_sources
    from ml.scripts.dataset_registry import inspect_dataset
except ModuleNotFoundError:
    from common import DATASET_ROOT, DATASET_TO_MODEL, EXPECTED_CLASSES
    from dataset_merge import merge_sources
    from dataset_registry import inspect_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect, validate, report, split, or merge SadakDrishti datasets.")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Inspect files, annotation format, and discovered classes")
    inspect.add_argument("--input", type=Path, required=True)
    for name in ("validate", "report"):
        command = commands.add_parser(name, help=f"Run {name} on a built-in or versioned dataset")
        command.add_argument("--dataset", required=True, help="vehicles/plates/helmets or version such as plate-v1")
        command.add_argument("--output", type=Path)
    split = commands.add_parser("split", help="Dispatch remaining arguments to split_dataset.py")
    split.add_argument("arguments", nargs=argparse.REMAINDER)
    merge = commands.add_parser("merge", help="Merge canonical, split datasets into one version")
    merge.add_argument("--type", choices=tuple(EXPECTED_CLASSES), required=True)
    merge.add_argument("--source", action="append", required=True, help="Registered source ID or dataset path; repeatable")
    merge.add_argument("--output-version", required=True)
    merge.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "inspect":
        print(json.dumps(inspect_dataset(args.input), indent=2, ensure_ascii=False)); return 0
    if args.command == "merge":
        print(json.dumps(merge_sources(args.type, args.source, args.output_version, args.output), indent=2, ensure_ascii=False)); return 0
    if args.command in {"validate", "report"}:
        script = Path(__file__).with_name("validate_dataset.py" if args.command == "validate" else "dataset_report.py")
        command = [sys.executable, str(script)]
        if args.dataset in DATASET_TO_MODEL:
            command.extend(["--dataset", args.dataset])
        else:
            model_type = args.dataset.split("-v", 1)[0]
            if model_type not in EXPECTED_CLASSES:
                raise SystemExit("Versioned datasets must look like vehicle-v1, plate-v1, or helmet-v1")
            data = DATASET_ROOT / "versions" / model_type / args.dataset / "data.yaml"
            if not data.is_file():
                raise SystemExit(f"Versioned dataset YAML does not exist: {data}")
            command.extend(["--data", str(data)])
        if args.output:
            command.extend(["--report" if args.command == "validate" else "--output", str(args.output)])
        return subprocess.run(command, check=False).returncode
    script = Path(__file__).with_name("split_dataset.py")
    return subprocess.run([sys.executable, str(script), *args.arguments], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
