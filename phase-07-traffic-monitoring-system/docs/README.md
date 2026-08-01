# TrafficOps — Web-connected traffic monitoring

The Phase 7 application now has two runtime surfaces:

- the original Tkinter program in `src/main.py`;
- the web-connected FastAPI runtime in `run_web.py`.

The FastAPI runtime owns one YOLO/ByteTrack processing worker and exposes its output through REST, MJPEG, and WebSocket. The React frontend consumes those interfaces; it never reads SQLite or Python process memory directly. A separate single-file worker can also analyze manually uploaded road footage or one public video link without writing its results to the live SQLite history.

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
- `WS /ws/live`

Uploaded and linked videos are limited to 500 MB by default, are processed from temporary storage, and are deleted when the analysis completes or fails. Linked videos are also limited to 120 minutes. Completed reports remain in process memory for six hours and are lost when the backend restarts.

Link ingestion accepts a single public video from an allowlisted source such as YouTube, Google Drive, Instagram, TikTok, Facebook, X, Vimeo, Twitch, Reddit, Loom, Dropbox, or OneDrive. It does not use cookies or credentials, and it rejects playlists, folders, live streams, private URLs, and private-network destinations. Extend the host allowlist for another trusted yt-dlp source with a comma-separated `TRAFFIC_ALLOWED_VIDEO_LINK_HOSTS` value.

## Speed calibration

`TRAFFIC_METERS_PER_PIXEL` converts tracked image displacement into physical distance. The default is only suitable for demonstrating the integration. For enforceable speed:

1. Fix the camera position, focal length, resolution, and frame rate.
2. Measure visible road reference distances.
3. Use perspective/homography calibration; a single scale is not accurate across image depth.
4. Compare results against a calibrated radar/LIDAR device.
5. Set the legal speed limit and preserve calibration/version audit records.

The current estimator smooths five displacement samples and rejects speeds above 200 km/h. It is operational telemetry, not certified enforcement evidence.

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
