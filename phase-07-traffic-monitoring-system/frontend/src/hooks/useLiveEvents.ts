import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { config } from "../lib/config";
import { nextMockDetection } from "../mocks/data";
import type { AlertRecord, ConnectionStatus, LiveEvent, VehicleDetection, ViolationEvent } from "../types";

const isDetection = (value: unknown): value is VehicleDetection => {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<VehicleDetection>;
  return typeof item.id === "number" && typeof item.trackingId === "number" &&
    typeof item.speed === "number" && (item.status === "NORMAL" || item.status === "OVERSPEED");
};

const isViolation = (value: unknown): value is ViolationEvent => {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<ViolationEvent>;
  return typeof item.id === "number" && typeof item.trackingId === "number" &&
    ["OVERSPEED", "NO_HELMET", "WRONG_LANE", "WRONG_DIRECTION"].includes(String(item.type));
};

const isAlert = (value: unknown): value is AlertRecord => {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<AlertRecord>;
  return typeof item.id === "number" && typeof item.trackingId === "number" &&
    ["LOW", "MEDIUM", "HIGH", "CRITICAL"].includes(String(item.severity)) &&
    ["NEW", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"].includes(String(item.status));
};

export function useLiveEvents() {
  const client = useQueryClient();
  const [connection, setConnection] = useState<ConnectionStatus>(config.useMocks ? "connected" : "reconnecting");
  const [latest, setLatest] = useState<VehicleDetection | null>(null);
  const [latestViolation, setLatestViolation] = useState<ViolationEvent | null>(null);
  const [latestAlert, setLatestAlert] = useState<AlertRecord | null>(null);
  const [fps, setFps] = useState(27.4);
  const [analysisFps, setAnalysisFps] = useState(config.useMocks ? 15 : 0);
  const [activeTracks, setActiveTracks] = useState(0);
  const [activeDetections, setActiveDetections] = useState(0);
  const [sourceMode, setSourceMode] = useState<"configured" | "browser" | "demo">("configured");
  const [cameraName, setCameraName] = useState("");
  const [demoVideoId, setDemoVideoId] = useState<string | null>(null);
  const [demoPaused, setDemoPaused] = useState(false);
  const [demoProgress, setDemoProgress] = useState(0);
  const [demoDuration, setDemoDuration] = useState<number | null>(null);
  const seen = useRef(new Set<string>());
  const lastQueryRefresh = useRef(0);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let stopped = false;
    let attempts = 0;

    const receiveDetection = (detection: VehicleDetection) => {
      const key = `${detection.id}:${detection.detectedAt}`;
      if (seen.current.has(key)) return;
      seen.current.add(key);
      if (seen.current.size > 300) seen.current = new Set(Array.from(seen.current).slice(-150));
      if (detection.speedAvailable !== false) setLatest(detection);
      if (Date.now() - lastQueryRefresh.current >= 2000) {
        client.invalidateQueries({ queryKey: ["summary"] });
        client.invalidateQueries({ queryKey: ["vehicles"] });
        client.invalidateQueries({ queryKey: ["analytics"] });
        if (detection.plate) client.invalidateQueries({ queryKey: ["plates"] });
        lastQueryRefresh.current = Date.now();
      }
    };

    if (config.useMocks) {
      const tick = () => {
        receiveDetection(nextMockDetection());
        setFps((value) => Number((value === 29.1 ? 27.4 : value + 0.1).toFixed(1)));
        timer = setTimeout(tick, 4500);
      };
      timer = setTimeout(tick, 1800);
      return () => { if (timer) clearTimeout(timer); };
    }

    const connect = () => {
      if (stopped) return;
      setConnection(attempts ? "reconnecting" : "reconnecting");
      socket = new WebSocket(config.wsUrl);
      socket.onopen = () => { attempts = 0; setConnection("connected"); };
      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(String(message.data)) as LiveEvent;
          if (event.type === "vehicle_detection" && isDetection(event.data)) receiveDetection(event.data);
          if (event.type === "violation_event" && isViolation(event.data)) {
            setLatestViolation(event.data);
            client.invalidateQueries({ queryKey: ["violations"] });
            client.invalidateQueries({ queryKey: ["violation-summary"] });
            client.invalidateQueries({ queryKey: ["vehicles"] });
          }
          if (event.type === "alert_event" && isAlert(event.data)) {
            setLatestAlert(event.data);
            client.invalidateQueries({ queryKey: ["alerts"] });
            client.invalidateQueries({ queryKey: ["alert-summary"] });
            window.dispatchEvent(new CustomEvent("trafficops:new-alert", { detail: event.data }));
          }
          if (event.type === "system_status" && typeof event.data?.fps === "number") {
            setFps(event.data.fps);
            if (typeof event.data.analysisFps === "number") setAnalysisFps(event.data.analysisFps);
            if (typeof event.data.activeTracks === "number") setActiveTracks(event.data.activeTracks);
            if (typeof event.data.activeDetections === "number") setActiveDetections(event.data.activeDetections);
            if (event.data.sourceMode) setSourceMode(event.data.sourceMode);
            if (typeof event.data.cameraName === "string") setCameraName(event.data.cameraName);
            if (event.data.demoVideoId !== undefined) setDemoVideoId(event.data.demoVideoId);
            if (typeof event.data.demoPaused === "boolean") setDemoPaused(event.data.demoPaused);
            if (typeof event.data.demoProgress === "number") setDemoProgress(event.data.demoProgress);
            if (event.data.demoDurationSeconds !== undefined) setDemoDuration(event.data.demoDurationSeconds);
            setConnection(event.data.connection);
          }
        } catch {
          // Ignore malformed messages; a later valid event keeps the stream usable.
        }
      };
      socket.onerror = () => socket?.close();
      socket.onclose = (event) => {
        if (stopped) return;
        if (event.code === 4401) {
          window.dispatchEvent(new Event("trafficops:unauthorized"));
          setConnection("offline");
          return;
        }
        attempts += 1;
        setConnection(attempts > 5 ? "offline" : "reconnecting");
        timer = setTimeout(connect, Math.min(1000 * 2 ** attempts, 30_000));
      };
    };
    connect();
    const resetLive = () => {
      setLatest(null);
      setLatestViolation(null);
      setLatestAlert(null);
      seen.current.clear();
      lastQueryRefresh.current = 0;
    };
    window.addEventListener("trafficops:reset-live", resetLive);
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      socket?.close();
      window.removeEventListener("trafficops:reset-live", resetLive);
    };
  }, [client]);

  return { connection, latest, latestViolation, latestAlert, fps, analysisFps, activeTracks, activeDetections, sourceMode, cameraName, demoVideoId, demoPaused, demoProgress, demoDuration };
}
