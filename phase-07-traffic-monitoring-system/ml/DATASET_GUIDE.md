# Nepal traffic dataset acquisition and quality guide

## Responsible sources

Look for candidate data in Kaggle, Roboflow Universe, academic/research repositories, official/open
datasets, institutional partnerships, and authorized local collection. Before importing, verify the
license, classes, annotation format, image quality, geographic relevance, duplicate level, and privacy
implications. Do not scrape arbitrary websites or assume that public access grants training/commercial
rights. `UNKNOWN` licenses remain blocked for production/commercial clearance until reviewed.

For local footage, use only authorized recordings, minimize retention, restrict access, and do not publish
raw faces or number plates without a lawful purpose and appropriate authorization. Never put sensitive
CCTV, extracted images, labels, or OCR crops in a public Git repository.

## Nepal coverage plan

Gradually collect independent sessions from Surkhet/Birendranagar and other authorized Nepal sites:
urban roads, highways, intersections, markets, college roads, narrow roads, and congestion. Include morning,
afternoon, evening, night, sun, shadow, rain, cloud, fog, dust, headlights, glare, compression, vibration,
and motion blur. Cover front, rear, elevated CCTV, side/intersection views, near, far, partial, crowded,
and occluded objects. Location names are planning examples—not claims that footage exists.

Diversity is more valuable than repeated adjacent frames. Sample roughly every 1–5 seconds, add dense
sampling only around rare events, and use duplicate review. Do not let one camera/video dominate.

Rough initial planning may target several thousand public/base examples plus 1,000+ Nepal-specific vehicle
examples, and several thousand plate/helmet examples where lawful data exists. Counts do not guarantee
accuracy: diversity beats duplicate volume, annotation quality beats raw count, and reviewed hard examples
beat easy repeated examples.

## Data roles

- `_raw/plates`: vehicle/frame images with `license_plate` boxes for the YOLO locator.
- `_raw/plate_chars`: cropped plates plus text transcriptions for a future OCR project. Never merge these
  into plate-object detection.
- `_raw/helmets`: rider/head ROI labels `helmet`/`no_helmet`.
- `_raw/vehicles`: six canonical road-user classes.
- `_raw/own_nepal`: authorized sampled footage pending task-specific annotation.

## Quality gates

A version is not training-ready until images decode, all label rows/classes/coordinates validate, mappings
are complete, critical orphans are absent, exact duplicates do not cross splits, source provenance remains,
the source-grouped 70/20/10 split exists, and its YAML resolves. Preserve a fixed Nepal-specific test set
with night, rain, distance, small plates, occlusion, crowded motorcycles, helmet ambiguity, blur, and poor
CCTV. Never use that test set for iterative training.

Production decisions must include false-violation rate, missed violations, plate/small-object recall,
no-helmet false accusations, bus/truck confusion, tracking stability, speed error, latency, and per-camera
performance—not only aggregate mAP.

For plate releases, explicitly slice plate recall by small/distant/night/glare conditions. For helmet
releases, report `no_helmet` recall plus helmet false-accusation and cap/hood confusion rates. For vehicle
releases, review motorcycle recall, car precision, bus/truck confusion, and small-object performance.
