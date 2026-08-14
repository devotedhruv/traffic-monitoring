"""Fine-tune the Nepal-specific SadakDrishti vehicle detector."""

try:
    from ml.scripts.train import parse_task_args, run_training
except ModuleNotFoundError:
    from train import parse_task_args, run_training


def main() -> int:
    args = parse_task_args("vehicle", "Fine-tune YOLO11 for Nepal vehicle and person detection.")
    run_training("vehicle", args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

