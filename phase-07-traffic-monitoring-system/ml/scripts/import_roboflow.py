"""Import a local Roboflow export or optionally download one with an environment API key."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

try:
    from ml.scripts.dataset_registry import DATASET_TYPES, import_local_source, safe_identifier
except ModuleNotFoundError:
    from dataset_registry import DATASET_TYPES, import_local_source, safe_identifier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a Roboflow YOLO export without exposing API credentials.")
    parser.add_argument("--input", type=Path, help="Already-downloaded Roboflow ZIP or dataset directory")
    parser.add_argument("--type", choices=DATASET_TYPES, required=True)
    parser.add_argument("--source-name", help="Stable source ID")
    parser.add_argument("--license", default="UNKNOWN")
    parser.add_argument("--notes", default="")
    parser.add_argument("--workspace", help="Roboflow workspace for optional API download")
    parser.add_argument("--project", help="Roboflow project for optional API download")
    parser.add_argument("--version", type=int, help="Roboflow dataset version for optional API download")
    parser.add_argument("--api-key-env", default="ROBOFLOW_API_KEY", help="Environment variable containing the API key")
    return parser.parse_args()


def _download(args: argparse.Namespace, output: Path) -> Path:
    if not (args.workspace and args.project and args.version):
        raise SystemExit("Provide --input, or provide --workspace, --project, and --version for API download.")
    api_key = os.getenv(args.api_key_env)
    if not api_key:
        raise SystemExit(f"Roboflow API key not found in {args.api_key_env}; it must stay outside source control.")
    try:
        from roboflow import Roboflow
    except ImportError as exc:
        raise SystemExit("Roboflow Python package is not installed. Use a local exported ZIP or install roboflow.") from exc
    try:
        dataset = Roboflow(api_key=api_key).workspace(args.workspace).project(args.project).version(args.version)
        downloaded = dataset.download("yolov11", location=str(output))
    except Exception as exc:
        raise SystemExit(f"Roboflow download failed ({type(exc).__name__}); credentials and response details were not logged.") from exc
    return Path(getattr(downloaded, "location", output))


def main() -> int:
    args = parse_args()
    if args.input is not None:
        source = args.input
        identifier = str(args.input.expanduser())
        default_name = args.input.stem
        temporary_context = None
    else:
        temporary_context = tempfile.TemporaryDirectory(prefix="sadakdrishti-roboflow-")
        source = _download(args, Path(temporary_context.name) / "dataset")
        identifier = f"{args.workspace}/{args.project}/{args.version}"
        default_name = f"{args.project}-v{args.version}"
    try:
        source_name = args.source_name or safe_identifier(default_name)
        destination, record, inspection = import_local_source(
            source, args.type, source_name, provider="Roboflow",
            source_identifier=identifier, license_name=args.license, notes=args.notes,
        )
    finally:
        if temporary_context is not None:
            temporary_context.cleanup()
    print(json.dumps({"destination": str(destination), "source": record, "inspection": inspection}, indent=2, ensure_ascii=False))
    if record["license"] == "UNKNOWN":
        print("WARNING: Roboflow source license is UNKNOWN. Verify it before training or production use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
