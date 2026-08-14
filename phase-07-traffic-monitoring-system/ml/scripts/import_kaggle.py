"""Authenticated Kaggle dataset importer with provenance and no credential logging."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

try:
    from ml.scripts.dataset_registry import DATASET_TYPES, import_local_source, safe_identifier
except ModuleNotFoundError:
    from dataset_registry import DATASET_TYPES, import_local_source, safe_identifier


def kaggle_auth_configured() -> bool:
    environment_auth = bool(os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"))
    config_auth = (Path.home() / ".kaggle" / "kaggle.json").is_file()
    return environment_auth or config_auth


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download a licensed Kaggle dataset into unvalidated raw storage.")
    parser.add_argument("--dataset", required=True, help="Kaggle identifier OWNER/DATASET")
    parser.add_argument("--type", choices=DATASET_TYPES, required=True)
    parser.add_argument("--source-name", help="Stable local source ID; defaults to the dataset slug")
    parser.add_argument("--license", default="UNKNOWN", help="Verified dataset license; UNKNOWN by default")
    parser.add_argument("--notes", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    executable = shutil.which("kaggle")
    if executable is None:
        raise SystemExit(
            "Kaggle CLI is unavailable. Install `kaggle`, then configure ~/.kaggle/kaggle.json "
            "or KAGGLE_USERNAME/KAGGLE_KEY. Credentials are never stored by SadakDrishti."
        )
    if not kaggle_auth_configured():
        raise SystemExit(
            "Kaggle authentication was not detected. Configure ~/.kaggle/kaggle.json with mode 600 "
            "or set KAGGLE_USERNAME and KAGGLE_KEY; do not add credentials to this repository."
        )
    source_name = args.source_name or safe_identifier(args.dataset.rsplit("/", 1)[-1])
    with tempfile.TemporaryDirectory(prefix="sadakdrishti-kaggle-") as temporary:
        download = Path(temporary) / "download"
        download.mkdir()
        completed = subprocess.run(
            [executable, "datasets", "download", "-d", args.dataset, "-p", str(download), "--unzip"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )
        if completed.returncode != 0:
            raise SystemExit(
                f"Kaggle download failed for {args.dataset} (exit {completed.returncode}); "
                "provider output was withheld to avoid exposing credential details."
            )
        destination, record, inspection = import_local_source(
            download, args.type, source_name, provider="Kaggle",
            source_identifier=args.dataset, license_name=args.license, notes=args.notes,
        )
    print(json.dumps({"destination": str(destination), "source": record, "inspection": inspection}, indent=2, ensure_ascii=False))
    if record["license"] == "UNKNOWN":
        print("WARNING: Kaggle source license is UNKNOWN. Verify it before training or commercial use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
