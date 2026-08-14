# Building Nepal-specific SadakDrishti datasets

SadakDrishti does not ship private CCTV footage or annotations. Build each dataset only from footage you
are authorized to process, follow the applicable privacy/retention rules, and keep raw media outside Git.

## Coverage plan

Collect independent recording sessions from urban roads, highways, intersections, narrow roads, and
congested roads. When permission and logistics allow, include different cities, districts, terrain, road
marking styles, and vehicle fleets across Nepal. A useful dataset must not be Kathmandu-only unless the
deployment is Kathmandu-only.

Record morning, afternoon, evening, and night. Cover bright sunlight, deep shadows, cloudy weather,
rain, fog, dust, headlights, CCTV compression, camera vibration, occlusion, and motion blur. Include front,
rear, elevated CCTV, side-angle, intersection, distant-vehicle, and close-vehicle views.

Create a collection log with at least:

- stable source/session identifier (never a secret camera URL);
- camera/site ID, date range, lighting/weather, resolution, and view;
- permission and retention status;
- whether the session is eligible for train, validation, or the fixed test set.

## Sample frames instead of extracting everything

Consecutive video frames are near-duplicates. Extracting every 30-FPS frame can let one short sequence
dominate training and create misleading validation results. Sample approximately every 1–5 seconds,
then deliberately add shorter intervals only around rare events. `extract_frames.py` defaults to two seconds
and records the source session in `frames.jsonl`:

```bash
python ml/scripts/extract_frames.py \
  --input videos/collection-session-01.mp4 \
  --output ml/datasets/_raw/own_nepal/session-01 \
  --every-seconds 2
```

The splitter keeps every frame from the same session in one split. Never manually scatter adjacent frames
across train, validation, and test. Keep the final test sessions fixed and untouched by model tuning.

## Expected YOLO layout

Each task has the same directory structure:

```text
ml/datasets/vehicles/
  images/{train,val,test}/
  labels/{train,val,test}/
```

Use `plates` and `helmets` for the other tasks. Each image must have a same-stem `.txt` label. A valid
YOLO detection row is:

```text
class_id x_center y_center width height
```

All four coordinates are normalized to `[0, 1]`. An intentional negative image uses an empty label file.
See [`../ANNOTATION_GUIDE.md`](../ANNOTATION_GUIDE.md) before annotation.

## Leakage-safe split

After annotation, split raw images by source session:

```bash
python ml/scripts/split_dataset.py \
  --input ml/datasets/raw/session-batch \
  --labels ml/datasets/raw/session-batch/labels \
  --manifest ml/datasets/raw/session-batch/frames.jsonl \
  --dataset vehicles \
  --require-labels
```

Default allocation is 70% train, 20% validation, and 10% test, with deterministic seed 42. The tool
writes `split_manifest.json`; preserve it as dataset-version evidence.

## Quality rules

1. Prefer local Nepal road footage representative of production cameras.
2. Keep source sessions independent across train/validation/test.
3. Include hard weather, lighting, blur, compression, occlusion, and congestion.
4. Fix label errors before adding epochs.
5. Review false positives and false negatives per camera and class.
6. Add manually reviewed hard examples to the next dataset version.
7. Keep a fixed final test set.
8. Compare against the current production model on that same test set.
9. Track dataset versions and collection provenance.
10. Never judge a detector using training loss alone.
