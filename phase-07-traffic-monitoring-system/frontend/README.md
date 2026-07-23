# TrafficOps Web Frontend

TrafficOps is the browser dashboard for the AI traffic-monitoring pipeline in the parent project. It provides a responsive control-room interface for a live annotated camera feed, vehicle metrics, speed violations, detection history, and analytics.

The current Python pipeline has no HTTP API, WebSocket server, or browser video endpoint. This frontend therefore runs in demo mode by default and isolates all future backend integration in `src/services`, `src/lib/config.ts`, and `src/hooks/useLiveEvents.ts`.

## Requirements

- Node.js 20 or newer
- npm 10 or newer

## Start locally

```bash
cp .env.example .env
npm install
npm run dev
```

Open the local URL printed by Vite. `VITE_USE_MOCKS=true` makes every page usable without the Python application.

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | REST and MJPEG backend origin |
| `VITE_WS_URL` | `ws://localhost:8000/ws/live` | Real-time event socket |
| `VITE_USE_MOCKS` | `true` | Use deterministic demo data instead of the backend |

Set `VITE_USE_MOCKS=false` only after the backend contract below is available. API failures remain visible in real mode.

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

## Recommended backend step

Add a small FastAPI layer beside the existing Python pipeline. It should expose read-only REST queries over SQLite, publish annotated OpenCV frames as MJPEG, configure CORS for the frontend origin, and send detection/system events through WebSocket. The React application never accesses SQLite or Python process memory directly.

The existing Tkinter dashboard and computer-vision pipeline are intentionally unchanged.
