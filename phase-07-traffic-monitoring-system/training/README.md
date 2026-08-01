# TrafficOps model training

The runtime now uses `models/yolo11s.pt` as a stronger generic baseline. Reliable local
results still require fine-tuning on frames from the deployed cameras. The repository
does not contain private annotations, so it does not pretend that plate or helmet
models are available.

## Dataset layout

Create one dataset for each task using Ultralytics YOLO labels:

```text
datasets/vehicles/
  images/{train,val,test}/
  labels/{train,val,test}/
```

Use the same layout for `datasets/plates` and `datasets/helmets`. Keep entire source
videos in one split to avoid near-duplicate frames leaking from train into validation.
The validation and test sets should include every deployed camera, dawn/day/night,
rain, glare, congestion, occlusion, small distant vehicles, and camera vibration.

For vehicles, label the five runtime classes exactly as defined in
`training/datasets/vehicles.yaml`. For plates, label the complete visible plate, even
when partially occluded. For helmets, label `helmet` and `no_helmet` around the rider's
head; do not infer a label when the head is not visible.

## Train and evaluate

Use a CUDA GPU for practical training:

```bash
source .venv/bin/activate
python training/train_model.py --task vehicle --data training/datasets/vehicles.yaml
python training/train_model.py --task plate --data training/datasets/plates.yaml
python training/train_model.py --task helmet --data training/datasets/helmets.yaml
```

Do not select weights only by overall mAP. Review per-camera precision/recall, small
object recall, false positives per hour, ID switches, line-crossing count error, and
speed error against radar/LIDAR ground truth. Keep a camera/date holdout that is never
used for tuning.

## Configure the runtime

Copy validated weights from each run's `weights/best.pt` into a controlled model
directory and set:

```env
TRAFFIC_MODEL_PATH=models/trafficops-vehicle-best.pt
TRAFFIC_PLATE_MODEL_PATH=models/trafficops-plate-best.pt
TRAFFIC_HELMET_MODEL_PATH=models/trafficops-helmet-best.pt
TRAFFIC_TESSERACT_CMD=tesseract
```

Plate recognition is available only when both dedicated plate weights and Tesseract
OCR are installed. Helmet detection is available only when dedicated helmet weights
exist. The API reports these capabilities so the interface never shows fabricated
specialist results.
