"""Backward-compatible wrapper for the SadakDrishti ML training subsystem."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ml.scripts.train import add_training_arguments, run_training


def parse_args() -> tuple[str, argparse.Namespace]:
    compatibility = argparse.ArgumentParser(
        description="Compatibility wrapper; prefer ml/scripts/train_<task>.py for new runs.",
        add_help=False,
    )
    compatibility.add_argument("--task", choices=("vehicle", "plate", "helmet"), required=True)
    task, remaining = compatibility.parse_known_args()
    parser = argparse.ArgumentParser(description=f"Train the SadakDrishti {task.task} detector")
    add_training_arguments(parser, task.task)
    parser.add_argument("--base-model", dest="model", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    parser.add_argument("--image-size", dest="imgsz", type=int, default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    args = parser.parse_args(remaining)
    return task.task, args


def main() -> int:
    task, args = parse_args()
    run_training(task, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
