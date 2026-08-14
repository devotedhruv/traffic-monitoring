# SadakDrishti custom-model lifecycle

This directory is the isolated, production-oriented development subsystem for three Ultralytics YOLO11
detectors: Nepal traffic vehicles, Nepal license-plate localization, and rider helmet/no-helmet detection.
It reuses—not replaces—the production ByteTrack, homography speed, plate preprocessing/OCR/voting,
helmet rider-ROI, lane-rule, FastAPI, and SQLite pipeline.

No private dataset or trained specialist weights are present. Commands validate this and stop clearly;
they never invent training results.

## Setup

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r ml/requirements-ml.txt
```

CUDA requires a PyTorch build compatible with your GPU/driver; follow PyTorch's official installation
instructions before installing the remaining requirements. CPU tooling and training use `--device cpu`.
Practical full training normally needs a GPU.

For Nepal plate OCR install Tesseract and both language packs, for example on Debian/Ubuntu:

```bash
sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-nep
```

SadakDrishti requests `nep+eng` by default and safely uses installed languages. OCR is a separate production
stage; these scripts train only the plate locator.

## Datasets

Read [`DATASET_GUIDE.md`](DATASET_GUIDE.md), [`datasets/README.md`](datasets/README.md), and
[`ANNOTATION_GUIDE.md`](ANNOTATION_GUIDE.md).
Put images and same-stem YOLO labels in:

```text
ml/datasets/vehicles/{images,labels}/{train,val,test}/
ml/datasets/plates/{images,labels}/{train,val,test}/
ml/datasets/helmets/{images,labels}/{train,val,test}/
```

Real media/labels are Git-ignored. Dataset YAML class order is fixed in `configs/*.yaml`.

Extract representative frames (two-second default, adjacent duplicate reduction, source manifest):

```bash
python ml/scripts/extract_frames.py \
  --input traffic.mp4 \
  --output ml/datasets/_raw/own_nepal/surkhet_day_01 \
  --every-seconds 2 --camera-id surkhet_cam_01 \
  --session-id surkhet_day_01 --location-label Surkhet \
  --license UNKNOWN --authorization-notes "Replace with verified authorization record"
```

Use `split_dataset.py` with `frames.jsonl`; grouping prioritizes source video, then session, camera, and
sequence so neighboring footage does not leak across train/validation/test.

## First-time dataset workflow

Import a public source without assuming its license:

```bash
python ml/scripts/import_kaggle.py --dataset OWNER/DATASET --type plate --license UNKNOWN
python ml/scripts/import_roboflow.py --input ~/Downloads/helmet-export.zip --type helmet --source-name helmet-source-v1
python ml/scripts/import_local.py --input /path/to/dataset --type plate --source-name own-plate-export-v1
```

Images-only imports are recorded as `needs_annotation`. Annotate them in CVAT, Roboflow, or Label Studio,
export YOLO detection, and import that export. Then preserve raw data while normalizing/remapping:

```bash
python ml/scripts/normalize_dataset.py \
  --input ml/datasets/_raw/plates/own-plate-export-v1 \
  --output ml/datasets/_processed/plates/own-plate-export-v1 \
  --source-id own-plate-export-v1

python ml/scripts/remap_classes.py \
  --dataset ml/datasets/_processed/plates/own-plate-export-v1 \
  --type plate --mapping mapping.json \
  --output ml/datasets/_processed/plates/own-plate-canonical-v1
```

Check duplicates, create the grouped split, validate, preview, and report:

```bash
python ml/scripts/find_duplicates.py --input ml/datasets/_processed/plates/own-plate-canonical-v1 --perceptual
python ml/scripts/split_dataset.py --input <images> --labels <labels> --manifest <frames.jsonl> --dataset plates --require-labels
python ml/scripts/validate_dataset.py --data <version>/data.yaml
python ml/scripts/visualize_annotations.py --data <version>/data.yaml --split train --count 50
python ml/scripts/dataset_report.py --data <version>/data.yaml
```

Merge multiple already canonical, validated, split sources into a version (then validate the result):

```bash
python ml/scripts/dataset_cli.py merge --type plate \
  --source /path/to/source-a --source /path/to/source-b --output-version plate-v1
```

## Validate and inspect annotations

```bash
python ml/scripts/validate_dataset.py --dataset vehicles
python ml/scripts/validate_dataset.py --dataset plates
python ml/scripts/validate_dataset.py --dataset helmets

python ml/scripts/check_annotations.py --dataset vehicles
```

Critical label/image errors return non-zero. Annotation summaries and headless plots go under `ml/reports/`.

## Fine-tune YOLO11

All training starts from pretrained weights by default, uses deterministic seed 42, performs a dataset
preflight, and writes runs under `ml/runs/`. The task-specific augmentations are in
`configs/training_defaults.yaml`. Plate transforms are intentionally more conservative because small plate
geometry/text can be destroyed by aggressive perspective, mixup, or mosaic.

Vehicle:

```bash
python ml/scripts/train_vehicle.py \
  --model yolo11s.pt --epochs 100 --imgsz 640 --batch -1 --device 0
```

Plate:

```bash
python ml/scripts/train_plate.py \
  --model yolo11s.pt --epochs 150 --imgsz 960 --batch -1 --device 0
```

Try plate `--imgsz 640`, `960`, and `1280` as separate named experiments; compare recall, latency, and
memory instead of assuming the largest is best.

Helmet:

```bash
python ml/scripts/train_helmet.py \
  --model yolo11s.pt --epochs 120 --imgsz 640 --batch -1 --device 0
```

CPU example:

```bash
python ml/scripts/train_vehicle.py --device cpu --batch 4 --workers 2
```

The helmet model is trained for the existing flow: vehicle detector → motorcycle/person association →
rider/head ROI → helmet detector. Production does not unnecessarily run it over every full frame.

## Evaluate and compare

Use the untouched test set for release decisions:

```bash
python ml/scripts/evaluate_model.py \
  --model ml/runs/plate/plate-experiment/weights/best.pt \
  --data ml/configs/plate.yaml \
  --split test --imgsz 960 --device 0

python ml/scripts/compare_models.py \
  --model-a ml/models/plate/plate-v1.pt --model-b ml/models/plate/plate-v2.pt \
  --data ml/configs/plate.yaml --imgsz 960 --device 0
```

Evaluation exports precision, recall, mAP50, mAP50-95, per-class metrics, confusion matrix artifacts,
false-positive/false-negative counts where exposed by Ultralytics, inference latency, and file size.
Comparison never promotes automatically: a marginal mAP increase can still lose critical recall, exceed
latency budget, or regress a Nepal camera/site.

## Hard examples and active learning

Mine uncertain examples without storing every frame:

```bash
python ml/scripts/collect_hard_examples.py \
  --type plate --model ml/models/plate/plate-v1.pt \
  --input authorized-review-footage/ --camera-id camera-01 \
  --low-confidence 0.15 --high-confidence 0.55 --manual-review
```

Supplying `--labels` enables objective FP/FN/wrong-class matching; without labels, the tool collects only
uncertain predictions and never pretends they are confirmed errors. Frames are sampled, perceptually
deduplicated, capped, timestamped, and written to the requested hard-example categories with JSONL
provenance. A human must review them before annotation/retraining.

The intended loop is:

```text
Production CCTV → inference → uncertain/wrong candidates → manual review
→ corrected annotations → Dataset V2 → retrain → fixed-test evaluation
→ compare with production → manually promote only if operationally better
```

## Benchmark, register, and promote

Validated weights are not committed by default. Registering copies a versioned file under
`ml/models/<type>/` and appends metadata including base model, dataset version, hyperparameters, metrics,
date, notes, and current Git commit:

```bash
python ml/scripts/benchmark_model.py --model <best.pt> --source <representative-media> --device cpu
python ml/scripts/register_model.py --type plate --model <best.pt> --version plate-v1 \
  --base-model yolo11s.pt --dataset-version plate-v1 --metrics <report>/metrics.json \
  --training-metadata <run>/sadakdrishti-training.json
python ml/scripts/promote_model.py --type plate --model ml/models/plate/plate-v1.pt
```

Registration accepts actual evaluation outputs only. Promotion requires a matching registered task,
training/evaluation dataset metadata, complete precision/recall/mAP metrics, and a readable repository-local
weight. It records the previous production version and never auto-selects a candidate.

Runtime production paths are existing settings: `TRAFFIC_VEHICLE_MODEL_PATH`,
`TRAFFIC_PLATE_MODEL_PATH`, and `TRAFFIC_HELMET_MODEL_PATH`. Plate/helmet weights are optional; missing
files disable only those specialists. Existing `/api/health` and authenticated `/api/capabilities` report
configured/loaded model versions, OCR backend/languages/readiness, tracker config, and calibration status
without exposing private paths.

Promotion updates `.env` with repository-relative paths; it never writes developer-machine absolute paths.
Vehicle promotion updates the common vehicle override and both legacy path keys for compatibility. Plate and
helmet use their existing optional keys. Review the diff and restart the backend. Missing custom plate or
helmet weights still disable only that specialist; vehicle monitoring remains alive.

## Operational references

- [`TRACKING_TUNING.md`](TRACKING_TUNING.md): ByteTrack tuning; ByteTrack is not trained.
- [`SPEED_CALIBRATION.md`](SPEED_CALIBRATION.md): calibrated geometry, not an AI speed model.
- [`LANE_CALIBRATION.md`](LANE_CALIBRATION.md): current calibrated lane-rule workflow.
- [`ACTIVE_LEARNING.md`](ACTIVE_LEARNING.md): reviewed hard-example lifecycle.

## Release-quality principles

Prefer local representative footage; isolate source sessions; include difficult conditions; correct labels
before adding epochs; review per-class FP/FN; feed reviewed hard examples into later versions; preserve a
fixed test set; compare with production; and never use training loss alone as a release criterion.
