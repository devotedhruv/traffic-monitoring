# TrafficOps — Web-connected traffic monitoring

The Phase 7 application now has two runtime surfaces:

- the original Tkinter program in `src/main.py`;
- the web-connected FastAPI runtime in `run_web.py`.

The FastAPI runtime owns one YOLO tracking worker and exposes its output through REST, MJPEG, and WebSocket. The React frontend consumes those interfaces; it never reads SQLite or Python process memory directly. A separate single-file worker analyzes uploaded road footage without writing its results to live SQLite history. Upload analysis uses YOLO11s, BoT-SORT, track lifecycle validation, optional feature-based camera stabilization, required four-point road-plane calibration, line crossing, robust ground-plane speed trajectories, and temporary annotated evidence video.

For live cameras, capture and browser streaming remain independent from AI inference and a latest-frame queue prevents stale analysis from slowing the feed. Prerecorded files default to ordered analysis instead: sampled media frames are processed sequentially so ByteTrack identities and media timestamps remain suitable for speed estimation even on a CPU-only machine. This makes file playback advance at inference speed rather than wall-clock speed; set `TRAFFIC_LIVE_ACCURATE_FILE_MODE=false` when real-time demo playback matters more than speed quality. The dashboard reports stream FPS and AI-analysis FPS separately. The eye button below the feed switches between annotated and clean video while detection, tracking, speed measurement, persistence, and alerts continue in the background. On first use, an oversized file is converted to a reusable proxy under `output/live-cache`. Live monitoring defaults to `yolov8n.pt` at 640 px, a 0.10 confidence threshold, and a high-recall ByteTrack profile. The bundled `traffic.mp4` also receives a central-road perspective profile (13 m × 50 m); adjust `TRAFFIC_LIVE_ROAD_POINTS`, `TRAFFIC_LIVE_ROAD_WIDTH_METERS`, and `TRAFFIC_LIVE_ROAD_LENGTH_METERS` when a surveyed site measurement is available. Override `TRAFFIC_LIVE_FILE_ANALYSIS_FPS`, `TRAFFIC_LIVE_MODEL_PATH`, `TRAFFIC_LIVE_IMAGE_SIZE`, `TRAFFIC_LIVE_CONFIDENCE`, `TRAFFIC_LIVE_STREAM_FPS`, `TRAFFIC_LIVE_STREAM_WIDTH`, `TRAFFIC_LIVE_TRACKER`, or `TRAFFIC_LIVE_PREPROCESS_FILES` when hardware and accuracy requirements differ.

## Local development

From `phase-07-traffic-monitoring-system`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python run_web.py
```

In a second terminal:

```bash
cd frontend
cp .env.example .env
```

Set `VITE_USE_MOCKS=false`, then run:

```bash
npm install
npm run dev
```

Open `http://localhost:5173`. API documentation is available at `http://localhost:8000/docs`.

## One-command container deployment

Docker Compose serves the whole application through one origin:

```bash
docker compose up --build
```

Open `http://localhost:8080`. Nginx serves React and proxies `/api`, `/ws`, and the MJPEG stream to FastAPI.

For an RTSP camera, set `TRAFFIC_VIDEO_SOURCE` in a root `.env` file:

```env
TRAFFIC_VIDEO_SOURCE=rtsp://camera-user:camera-password@192.168.1.50:554/stream1
TRAFFIC_SPEED_LIMIT=50
TRAFFIC_METERS_PER_PIXEL=0.05
TRAFFICOPS_PORT=8080
```

Do not commit real camera credentials. Use a deployment secret manager in production.

## API

- `GET /api/health`
- `GET /api/dashboard/summary`
- `GET /api/vehicles`
- `GET /api/vehicles/{id}`
- `GET /api/plates` for confirmed OCR reads joined to their tracked vehicle records
- `GET /api/analytics?range=today`
- `GET /api/cameras`
- `POST /api/cameras/browser/start` and `POST /api/cameras/{camera_id}/stop`
- `GET|POST /api/cameras/{camera_id}/calibration`
- `GET /api/cameras/{camera_id}/stream`
- `POST /api/video-analysis` with a raw video body and filename/calibration query parameters
- `GET /api/video-analysis/{job_id}`
- `GET /api/video-analysis/{job_id}/video` for the temporary annotated H.264 result
- `WS /ws/live`
- `WS /ws/cameras/{camera_id}/ingest` for authenticated, timestamped browser JPEG frames

Uploaded videos are limited to 500 MB by default, are processed from temporary storage,
and are deleted when the analysis completes or fails. Completed reports remain in
process memory for six hours and are lost when the backend restarts.

The dashboard can also use a browser webcam. Open **Browser webcam**, grant camera
permission, choose a device, and connect. Browser camera access requires `localhost`
or HTTPS. The client sends at most one frame at a time and the backend keeps only the
newest pending frames, preventing delayed results when inference is slower than the
camera. Browser and configured-video road calibrations are stored separately.

## Perspective and speed calibration

Uploaded videos can mark four normalized image points in this order: far-left,
far-right, near-right, and near-left. Enter the measured road width and length between
those points. OpenCV computes a homography from image pixels to ground-plane metres;
the tracker then measures vehicle bottom-centre trajectories in that plane. A movable
count line provides more stable unique crossing counts.

If calibration is disabled, `TRAFFIC_METERS_PER_PIXEL` converts tracked image
displacement into physical distance. This fallback is explicitly reported as low
confidence and is only suitable for integration testing. For operational speed:

1. Fix the camera position, focal length, resolution, and frame rate.
2. Measure visible road reference distances.
3. Recalibrate each camera after its zoom, position, crop, or resolution changes.
4. Compare results against a calibrated radar/LIDAR device.
5. Set the legal speed limit and preserve calibration/version audit records.

The estimator uses a trimmed trajectory average, acceleration/outlier rejection, and
validated track lifecycles. It remains operational telemetry, not certified
enforcement evidence, until it is independently validated and approved for the local
legal context.

## Custom and specialist models

`models/yolo11s.pt` is the stronger generic baseline. It is not a substitute for local
fine-tuning. See `training/README.md` for camera-specific vehicle, plate, and helmet
dataset conventions and training commands. The optional specialist environment
variables are:

```env
TRAFFIC_PLATE_MODEL_PATH=models/trafficops-plate-best.pt
TRAFFIC_PLATE_OCR_ENGINE=tesseract
TRAFFIC_PLATE_OCR_LANGUAGES=eng
TRAFFIC_PLATE_CONFIDENCE=0.35
TRAFFIC_PLATE_MIN_QUALITY=0.18
TRAFFIC_PLATE_SAMPLE_SECONDS=0.75
TRAFFIC_HELMET_MODEL_PATH=models/trafficops-helmet-best.pt
TRAFFIC_LIVE_HELMET_CONFIDENCE=0.35
TRAFFIC_LIVE_HELMET_CONFIRMATIONS=3
TRAFFIC_LIVE_HELMET_SAMPLE_SECONDS=0.75
TRAFFIC_TESSERACT_CMD=tesseract
```

Number-plate OCR and helmet violations remain unavailable until those validated
weights are supplied. The result API exposes a capability map, and the frontend shows
"not configured" instead of generating placeholder results. Live helmet inspection is
limited to a person associated with a tracked motorcycle, samples the rider head crop,
and requires repeated recent `no_helmet` observations before emitting one event per
track.

Live number-plate recognition runs the dedicated detector only inside each tracked
vehicle crop, quality-gates the plate image, and confirms text only after consistent
OCR observations across frames. A confirmed plate, OCR confidence, and evidence crop
are written back to that vehicle's database row and shown together in the dashboard's
Number Plate Recognition section. Generic vehicle weights are intentionally not used
to invent a plate value.

For Devanagari OCR, install the Nepali Tesseract language data and set
`TRAFFIC_PLATE_OCR_LANGUAGES=eng+nep`.

Wrong-lane monitoring also remains "not configured" until measured camera-specific
lane rules are saved through `POST /api/cameras/{camera_id}/lanes` or supplied as a
JSON array in `TRAFFIC_LIVE_LANE_RULES`. Every rule uses normalized calibrated-road
width boundaries (`minX`, `maxX`), an `allowedDirection`, optional
`allowedVehicleTypes`, and `boundaryTolerance`. For example, after replacing the
boundaries and rules with surveyed site values:

```json
[
  {"laneId":1,"minX":0.0,"maxX":0.5,"allowedDirection":"approaching","allowedVehicleTypes":["car","motorcycle"],"boundaryTolerance":0.03},
  {"laneId":2,"minX":0.5,"maxX":1.0,"allowedDirection":"moving_away","allowedVehicleTypes":[],"boundaryTolerance":0.03}
]
```

The example is schema documentation, not a rule for the bundled video. Configure only
measured legal lane rules. The evaluator ignores boundary points, immature/stationary
tracks, and short lane transitions; `WRONG_DIRECTION` uses the separate global
`TRAFFIC_LIVE_ALLOWED_DIRECTION` rule. Confirmed violations are deduplicated, stored
with evidence under `output/violations`, exposed by the violation APIs, and published
over the existing WebSocket.

## Real-world security and operations

- Put the application behind HTTPS and an authenticated reverse proxy before internet exposure.
- Restrict RTSP cameras and port 8000 to a private network.
- Add retention rules for plates, snapshots, and database backups.
- Confirm local privacy, surveillance, and evidence-handling requirements.
- Monitor `/api/health` and restart the container on failure.
- Use a UPS and hardware appropriate for continuous inference.
- Prefer an NVIDIA GPU and the correct container runtime for multi-camera/high-FPS deployments.
- Add per-camera workers and a proper database such as PostgreSQL before horizontally scaling.

## Verification

```bash
TRAFFIC_AUTOSTART=false .venv/bin/python -m unittest discover -s tests -v
cd frontend
npm run build
npm run lint
npm run test
```
