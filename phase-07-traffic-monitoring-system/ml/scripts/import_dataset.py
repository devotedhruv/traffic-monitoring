"""Convenience dispatcher for supported SadakDrishti dataset import providers."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Dispatch to local, Kaggle, or Roboflow importers; provider-specific flags follow the provider.",
    )
    parser.add_argument("provider", choices=("local", "kaggle", "roboflow"))
    return parser.parse_known_args()


def main() -> int:
    args, remaining = parse_args()
    script = Path(__file__).with_name(f"import_{args.provider}.py")
    return subprocess.run([sys.executable, str(script), *remaining], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
