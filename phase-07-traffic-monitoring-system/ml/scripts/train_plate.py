"""Fine-tune the plate-localization detector; OCR remains a separate stage."""

try:
    from ml.scripts.train import parse_task_args, run_training
except ModuleNotFoundError:
    from train import parse_task_args, run_training


def main() -> int:
    args = parse_task_args("plate", "Fine-tune YOLO11 to locate Nepal license plates (OCR is not trained here).")
    run_training("plate", args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

