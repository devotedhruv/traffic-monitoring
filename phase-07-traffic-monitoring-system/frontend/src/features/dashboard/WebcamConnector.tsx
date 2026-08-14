import { useEffect, useRef, useState } from "react";
import type { MouseEvent } from "react";
import { Camera, CircleStop, RotateCcw, Save, Undo2, Webcam } from "lucide-react";
import { cameraIngestWebSocketUrl, config } from "../../lib/config";
import { cx } from "../../lib/format";
import { api } from "../../services/api";
import type { LiveCameraCalibration, NormalizedPoint } from "../../types";

const defaultCalibration: LiveCameraCalibration = {
  sourcePoints: [],
  roadWidthMeters: 8,
  roadLengthMeters: 30,
  laneCount: 2,
  quality: 0.8
};

function releaseStream(stream: MediaStream | null) {
  stream?.getTracks().forEach((track) => track.stop());
}

export function WebcamConnector({ cameraId, onSourceChanged }: {
  cameraId: string;
  onSourceChanged?: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<number | null>(null);
  const browserStartedRef = useRef(false);
  const mountedRef = useRef(true);
  const [open, setOpen] = useState(false);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceId] = useState("");
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [calibration, setCalibration] = useState(defaultCalibration);
  const [savingCalibration, setSavingCalibration] = useState(false);
  const secureCameraContext = typeof window === "undefined" || window.isSecureContext || ["localhost", "127.0.0.1"].includes(window.location.hostname);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
      socketRef.current?.close();
      releaseStream(streamRef.current);
      if (browserStartedRef.current) void api.stopCamera(cameraId).catch(() => undefined);
    };
  }, [cameraId]);

  const refreshDevices = async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    const available = (await navigator.mediaDevices.enumerateDevices()).filter((device) => device.kind === "videoinput");
    if (!mountedRef.current) return;
    setDevices(available);
    setDeviceId((current) => current || available[0]?.deviceId || "");
  };

  const stopLocalCapture = () => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = null;
    socketRef.current?.close();
    socketRef.current = null;
    releaseStream(streamRef.current);
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setConnected(false);
  };

  const connect = async () => {
    if (!secureCameraContext) {
      setMessage("Browser webcam requires HTTPS or localhost.");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setMessage("This browser does not expose webcam access.");
      return;
    }
    setBusy(true);
    setMessage("Requesting camera permission…");
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
          width: { ideal: 960, max: 1280 },
          height: { ideal: 540, max: 720 },
          frameRate: { ideal: 10, max: 15 }
        }
      });
      streamRef.current = media;
      if (videoRef.current) {
        videoRef.current.srcObject = media;
        await videoRef.current.play();
      }
      await refreshDevices();
      const label = media.getVideoTracks()[0]?.label || "Browser Webcam";
      await api.startBrowserCamera(label);
      browserStartedRef.current = true;
      const browserCalibration = await api.getCameraCalibration(cameraId);
      if (mountedRef.current) {
        setCalibration(browserCalibration.calibration ?? defaultCalibration);
      }
      const socket = new WebSocket(cameraIngestWebSocketUrl(cameraId));
      socket.binaryType = "arraybuffer";
      socketRef.current = socket;
      let frameInFlight = false;
      const canvas = document.createElement("canvas");

      const schedule = () => {
        if (socketRef.current !== socket || socket.readyState !== WebSocket.OPEN) return;
        timerRef.current = window.setTimeout(sendFrame, 100);
      };
      const sendFrame = () => {
        const video = videoRef.current;
        if (!video || frameInFlight || socket.readyState !== WebSocket.OPEN || !video.videoWidth) {
          schedule();
          return;
        }
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext("2d", { alpha: false })?.drawImage(video, 0, 0);
        frameInFlight = true;
        canvas.toBlob(async (blob) => {
          if (!blob || socket.readyState !== WebSocket.OPEN) {
            frameInFlight = false;
            schedule();
            return;
          }
          const jpeg = new Uint8Array(await blob.arrayBuffer());
          const payload = new ArrayBuffer(8 + jpeg.byteLength);
          new DataView(payload).setFloat64(0, performance.now() / 1000, false);
          new Uint8Array(payload, 8).set(jpeg);
          socket.send(payload);
        }, "image/jpeg", 0.76);
      };
      socket.onopen = () => {
        if (!mountedRef.current) return;
        setConnected(true);
        setMessage("Webcam connected. Frames are being analyzed by the backend.");
        onSourceChanged?.();
        sendFrame();
      };
      socket.onmessage = () => {
        frameInFlight = false;
        schedule();
      };
      socket.onerror = () => socket.close();
      socket.onclose = (event) => {
        if (!mountedRef.current || socketRef.current !== socket) return;
        socketRef.current = null;
        releaseStream(streamRef.current);
        streamRef.current = null;
        if (videoRef.current) videoRef.current.srcObject = null;
        setConnected(false);
        frameInFlight = false;
        setMessage(event.code === 4401 ? "Webcam session expired. Sign in again." : "Webcam connection stopped.");
        if (browserStartedRef.current) {
          browserStartedRef.current = false;
          void api.stopCamera(cameraId).then(() => onSourceChanged?.()).catch(() => undefined);
        }
      };
    } catch (reason) {
      stopLocalCapture();
      if (browserStartedRef.current) {
        browserStartedRef.current = false;
        await api.stopCamera(cameraId).catch(() => undefined);
      }
      setMessage(reason instanceof Error ? reason.message : "Could not connect the webcam.");
    } finally {
      if (mountedRef.current) setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    stopLocalCapture();
    try {
      await api.stopCamera(cameraId);
      browserStartedRef.current = false;
      setMessage("Browser webcam stopped. The configured backend source was restored.");
      onSourceChanged?.();
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Could not stop the webcam source.");
    } finally {
      setBusy(false);
    }
  };

  const addPoint = (event: MouseEvent<HTMLDivElement>) => {
    if (!connected || calibration.sourcePoints.length >= 4) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const video = videoRef.current;
    if (!video?.videoWidth || !video.videoHeight) return;
    const scale = Math.min(bounds.width / video.videoWidth, bounds.height / video.videoHeight);
    const renderedWidth = video.videoWidth * scale;
    const renderedHeight = video.videoHeight * scale;
    const offsetX = (bounds.width - renderedWidth) / 2;
    const offsetY = (bounds.height - renderedHeight) / 2;
    const renderedX = event.clientX - bounds.left - offsetX;
    const renderedY = event.clientY - bounds.top - offsetY;
    if (renderedX < 0 || renderedY < 0 || renderedX > renderedWidth || renderedY > renderedHeight) return;
    const point = {
      x: Math.max(0, Math.min(1, renderedX / renderedWidth)),
      y: Math.max(0, Math.min(1, renderedY / renderedHeight))
    };
    setCalibration((current) => ({ ...current, sourcePoints: [...current.sourcePoints, point] }));
  };

  const updateNumber = (field: "roadWidthMeters" | "roadLengthMeters" | "laneCount", value: number) => {
    setCalibration((current) => ({ ...current, [field]: value }));
  };

  const saveCalibration = async () => {
    if (calibration.sourcePoints.length !== 4) return;
    setSavingCalibration(true);
    try {
      const response = await api.updateCameraCalibration(cameraId, calibration);
      setCalibration(response.calibration);
      setMessage("Road calibration saved. Speed now uses the measured road geometry.");
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Road calibration could not be saved.");
    } finally {
      setSavingCalibration(false);
    }
  };

  return <div className="border-t border-border bg-surface-secondary/35">
    <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} className="flex min-h-11 w-full items-center gap-2 px-3 text-left text-[11px] font-bold text-secondary hover:bg-elevated">
      <Webcam size={16} className="text-primary" /> Browser webcam
      <span className={cx("ml-auto rounded-full px-2 py-1 text-[9px]", connected ? "bg-success/10 text-success" : "bg-elevated text-muted")}>{connected ? "CONNECTED" : "OFF"}</span>
    </button>
    {open && <div className="grid gap-3 border-t border-border p-3 xl:grid-cols-[minmax(0,1.3fr)_minmax(260px,.7fr)]">
      <div>
        <div className="relative grid aspect-video min-h-52 place-items-center overflow-hidden rounded-xl border border-border bg-black" onClick={addPoint} role="presentation">
          <video ref={videoRef} muted playsInline className="h-full w-full object-contain" />
          {!connected && <div className="absolute inset-0 grid place-items-center p-5 text-center text-white/65"><div><Camera className="mx-auto mb-2" size={28} /><p className="text-xs font-semibold text-white">Connect this browser's webcam</p><p className="mt-1 text-[10px]">Frames stay live and are sent to your authenticated backend session.</p></div></div>}
          {connected && calibration.sourcePoints.map((point: NormalizedPoint, index: number) => <span key={`${point.x}-${point.y}-${index}`} className="pointer-events-none absolute grid h-7 w-7 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border-2 border-white bg-primary text-[10px] font-extrabold text-on-primary shadow" style={{ left: `${point.x * 100}%`, top: `${point.y * 100}%` }}>{index + 1}</span>)}
        </div>
        <p className="mt-2 text-[10px] text-muted">For calibrated speed, click road corners in order: far-left, far-right, near-right, near-left.</p>
      </div>
      <div className="space-y-3">
        <label className="block text-[10px] font-semibold text-muted">Camera device<select className="field mt-1 h-10 text-xs" value={deviceId} onChange={(event) => setDeviceId(event.target.value)} disabled={connected}>{devices.length ? devices.map((device, index) => <option key={device.deviceId} value={device.deviceId}>{device.label || `Camera ${index + 1}`}</option>) : <option value="">Default camera</option>}</select></label>
        <div className="grid grid-cols-3 gap-2">
          <label className="text-[9px] font-semibold text-muted">Width (m)<input className="field mt-1 h-9 px-2 text-xs" type="number" min="2" max="80" step="0.5" value={calibration.roadWidthMeters} onChange={(event) => updateNumber("roadWidthMeters", Number(event.target.value))} /></label>
          <label className="text-[9px] font-semibold text-muted">Length (m)<input className="field mt-1 h-9 px-2 text-xs" type="number" min="5" max="1000" step="1" value={calibration.roadLengthMeters} onChange={(event) => updateNumber("roadLengthMeters", Number(event.target.value))} /></label>
          <label className="text-[9px] font-semibold text-muted">Lanes<input className="field mt-1 h-9 px-2 text-xs" type="number" min="1" max="8" step="1" value={calibration.laneCount} onChange={(event) => updateNumber("laneCount", Number(event.target.value))} /></label>
        </div>
        <div className="flex flex-wrap gap-2">
          {!connected ? <button type="button" className="primary-button h-10 flex-1 px-3 text-xs" onClick={connect} disabled={busy || config.useMocks}><Webcam size={15} />{busy ? "Connecting…" : "Connect webcam"}</button> : <button type="button" className="secondary-button flex-1 text-danger" onClick={disconnect} disabled={busy}><CircleStop size={15} />Stop webcam</button>}
          <button type="button" className="icon-button h-10 w-10" onClick={() => setCalibration((current) => ({ ...current, sourcePoints: current.sourcePoints.slice(0, -1) }))} disabled={!calibration.sourcePoints.length} aria-label="Undo calibration point"><Undo2 size={15} /></button>
          <button type="button" className="icon-button h-10 w-10" onClick={() => setCalibration((current) => ({ ...current, sourcePoints: [] }))} disabled={!calibration.sourcePoints.length} aria-label="Reset calibration points"><RotateCcw size={15} /></button>
        </div>
        <button type="button" className="secondary-button w-full" onClick={saveCalibration} disabled={calibration.sourcePoints.length !== 4 || savingCalibration}><Save size={14} />{savingCalibration ? "Saving…" : `Save road calibration (${calibration.sourcePoints.length}/4)`}</button>
        {!secureCameraContext && <p className="rounded-lg border border-warning/25 bg-warning/10 p-2 text-[10px] text-warning">Use HTTPS or localhost so the browser can grant camera permission.</p>}
        {message && <p role="status" className="rounded-lg border border-border bg-surface p-2 text-[10px] text-muted">{message}</p>}
      </div>
    </div>}
  </div>;
}
