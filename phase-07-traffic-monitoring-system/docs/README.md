# TrafficOps — Web-connected traffic monitoring

The Phase 7 application now has two runtime surfaces:

- the original Tkinter program in `src/main.py`;
- the web-connected FastAPI runtime in `run_web.py`.

The FastAPI runtime owns one YOLO tracking worker and exposes its output through REST, MJPEG, and WebSocket. The React frontend consumes those interfaces; it never reads SQLite or Python process memory directly. A separate single-file worker analyzes uploaded road footage or one public video link without writing its results to live SQLite history. Upload analysis uses YOLO11s, BoT-SORT, track lifecycle validation, optional feature-based camera stabilization, four-point road-plane calibration, line crossing, ground-plane speed trajectories, and temporary annotated evidence video.

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
- `GET /api/analytics?range=today`
- `GET /api/cameras`
- `GET /api/cameras/{camera_id}/stream`
- `POST /api/video-analysis` with a raw video body and filename/calibration query parameters
- `POST /api/video-analysis/link` with a public link, rights confirmation, and calibration JSON
- `GET /api/video-analysis/{job_id}`
- `GET /api/video-analysis/{job_id}/video` for the temporary annotated H.264 result
- `WS /ws/live`

Uploaded and linked videos are limited to 500 MB by default, are processed from temporary storage, and are deleted when the analysis completes or fails. Linked videos are also limited to 120 minutes. Completed reports remain in process memory for six hours and are lost when the backend restarts.

Link ingestion accepts a single public video from an allowlisted source such as YouTube, Google Drive, Instagram, TikTok, Facebook, X, Vimeo, Twitch, Reddit, Loom, Dropbox, or OneDrive. It does not use cookies or credentials, and it rejects playlists, folders, live streams, private URLs, and private-network destinations. Extend the host allowlist for another trusted yt-dlp source with a comma-separated `TRAFFIC_ALLOWED_VIDEO_LINK_HOSTS` value.

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
TRAFFIC_HELMET_MODEL_PATH=models/trafficops-helmet-best.pt
TRAFFIC_TESSERACT_CMD=tesseract
```

Number-plate OCR and helmet violations remain unavailable until those validated
weights are supplied. The result API exposes a capability map, and the frontend shows
"not configured" instead of generating placeholder results. Wrong-direction events
use the selected allowed direction and the calibrated ground-plane trajectory.

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
