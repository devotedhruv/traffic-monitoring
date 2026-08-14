# Active learning and model growth

```text
Authorized production footage
        ↓
Current registered model
        ↓
mistakes / uncertain predictions (sampled and deduplicated)
        ↓
manual privacy and correctness review
        ↓
correct YOLO annotation
        ↓
Dataset V2 (old fixed test unchanged)
        ↓
retrain from pretrained YOLO11 weights
        ↓
evaluate against fixed Nepal test set
        ↓
compare accuracy, error cost, latency, size, and camera behavior
        ↓
register and promote only after human approval
```

`collect_hard_examples.py` stores sparse candidates and provenance; it does not turn model predictions into
ground truth. Review `false_positive`, `false_negative`, `wrong_class`, `low_confidence`, `missed`,
`poor_crop`, `false_helmet`, `false_no_helmet`, and `difficult_head` cases before annotation. Keep source,
camera, timestamp, track ID, predicted class, and confidence where available.

Do not merely add epochs when labels are wrong. Track dataset/model versions, compare every candidate with
the current production model, and investigate regressions by camera and difficult-condition slices.

