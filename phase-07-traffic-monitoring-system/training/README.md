# Legacy training entry point

The production-oriented SadakDrishti training subsystem now lives in [`../ml`](../ml/README.md).
`training/train_model.py` remains as a compatibility wrapper for existing automation; it forwards
to the same validation, augmentation, and YOLO11 fine-tuning implementation used by the task-specific
commands.

New work should use:

```bash
python ml/scripts/train_vehicle.py --device 0
python ml/scripts/train_plate.py --device 0
python ml/scripts/train_helmet.py --device 0
```

No private dataset or specialist weights are bundled with the repository.
