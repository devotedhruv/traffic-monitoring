import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { config } from "../lib/config";
import { nextMockDetection } from "../mocks/data";
import type { ConnectionStatus, LiveEvent, VehicleDetection } from "../types";

const isDetection = (value: unknown): value is VehicleDetection => {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<VehicleDetection>;
  return typeof item.id === "number" && typeof item.trackingId === "number" &&
    typeof item.speed === "number" && (item.status === "NORMAL" || item.status === "OVERSPEED");
};

export function useLiveEvents() {
  const client = useQueryClient();
  const [connection, setConnection] = useState<ConnectionStatus>(config.useMocks ? "connected" : "reconnecting");
  const [latest, setLatest] = useState<VehicleDetection | null>(null);
  const [fps, setFps] = useState(27.4);
  const seen = useRef(new Set<string>());

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
      setLatest(detection);
      client.invalidateQueries({ queryKey: ["summary"] });
      client.invalidateQueries({ queryKey: ["vehicles"] });
      client.invalidateQueries({ queryKey: ["analytics"] });
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
          if (event.type === "system_status" && typeof event.data?.fps === "number") {
            setFps(event.data.fps);
            setConnection(event.data.connection);
          }
        } catch {
          // Ignore malformed messages; a later valid event keeps the stream usable.
        }
      };
      socket.onerror = () => socket?.close();
      socket.onclose = () => {
        if (stopped) return;
        attempts += 1;
        setConnection(attempts > 5 ? "offline" : "reconnecting");
        timer = setTimeout(connect, Math.min(1000 * 2 ** attempts, 30_000));
      };
    };
    connect();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      socket?.close();
    };
  }, [client]);

  return { connection, latest, fps };
}
