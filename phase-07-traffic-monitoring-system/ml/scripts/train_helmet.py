"""Fine-tune the helmet specialist used only on rider/head regions."""

try:
    from ml.scripts.train import parse_task_args, run_training
except ModuleNotFoundError:
    from train import parse_task_args, run_training


def main() -> int:
    args = parse_task_args("helmet", "Fine-tune YOLO11 for helmet/no_helmet rider-region inference.")
    run_training("helmet", args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

