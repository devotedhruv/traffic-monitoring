# TrafficOps Web Frontend

TrafficOps is the browser dashboard for the AI traffic-monitoring pipeline in the parent project. It provides a responsive control-room interface for a live annotated camera feed, vehicle metrics, speed violations, detection history, analytics, and isolated analysis from a locally uploaded video clip.

The Python project now includes a FastAPI integration in `../web` with REST, WebSocket, and MJPEG endpoints. The frontend can use that service or run independently in demo mode.

## Requirements

- Node.js 20 or newer
- npm 10 or newer

## Start locally

```bash
cp .env.example .env
npm install
npm run dev
```

Open the local URL printed by Vite. Use `VITE_USE_MOCKS=false` with `python ../run_web.py`; set it to `true` to develop without the Python application.

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | REST and MJPEG backend origin |
| `VITE_WS_URL` | `ws://localhost:8000/ws/live` | Real-time event socket |
| `VITE_USE_MOCKS` | `true` | Use deterministic demo data instead of the backend |

API failures remain visible in real mode.

## Commands

```bash
npm run dev
npm run build
npm run preview
npm run lint
npm run test
```

The production output is generated in `dist/` and should be served by a static host configured to fall back to `index.html` for React Router paths.

## Backend contract

- `GET /api/health`
- `GET /api/dashboard/summary`
- `GET /api/vehicles?page=1&pageSize=20&status=&type=&search=&sort=time_desc`
- `GET /api/vehicles/:id`
- `GET /api/analytics?range=today`
- `GET /api/cameras`
- `GET /api/cameras/:cameraId/stream` (MJPEG)
- `POST /api/video-analysis?filename=...&location=...&speedLimit=...&metersPerPixel=...` (raw video body)
- `GET /api/video-analysis/:jobId`
- `WS /ws/live`

Example WebSocket detection event:

```json
{
  "type": "vehicle_detection",
  "data": {
    "id": 1024,
    "trackingId": 281,
    "vehicleType": "car",
    "plate": "BA 12 PA 1234",
    "speed": 68.4,
    "speedLimit": 50,
    "status": "OVERSPEED",
    "detectedAt": "2026-07-23T10:00:00Z",
    "cameraId": "camera-01",
    "cameraName": "North Junction",
    "snapshotUrl": null
  }
}
```

Example system-status event:

```json
{
  "type": "system_status",
  "data": {
    "connection": "connected",
    "fps": 27.4,
    "cameraId": "camera-01",
    "timestamp": "2026-07-23T10:00:00Z"
  }
}
```

## Backend

The FastAPI layer is implemented in `../web/api.py`, with the computer-vision worker in `../web/runtime.py`. Run it from the parent directory using `python run_web.py`. The React application never accesses SQLite or Python process memory directly, and the existing Tkinter dashboard remains available.
