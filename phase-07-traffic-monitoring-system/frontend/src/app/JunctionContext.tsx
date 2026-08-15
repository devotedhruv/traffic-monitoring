import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { api } from "../services/api";
import type { CameraConfig, DemoScenarioOption, DemoStatus, DemoVideo, Junction, SourceMode } from "../types";

/* eslint-disable react-refresh/only-export-components */
interface JunctionContextValue {
  junctions: Junction[];
  junctionCameras: CameraConfig[];
  selectedJunction: Junction | null;
  selectedCamera: CameraConfig | null;
  selectedJunctionId: string;
  selectedCameraId: string;
  sourceMode: SourceMode;
  demoVideos: DemoVideo[];
  selectedDemoVideo: DemoVideo | null;
  scenarioFilter: string;
  scenarios: DemoScenarioOption[];
  demoStatus: DemoStatus | null;
  streamVersion: number;
  eventDemoOpen: boolean;
  unavailableReason: string | null;
  selectJunction: (junctionId: string) => void;
  selectCamera: (cameraId: string) => void;
  setSourceMode: (mode: SourceMode) => void;
  setScenarioFilter: (scenario: string) => void;
  startDemo: (videoId?: string, cameraOverride?: string) => Promise<boolean>;
  stopDemo: () => Promise<void>;
  pauseDemo: () => Promise<void>;
  resumeDemo: () => Promise<void>;
  restartDemo: () => Promise<void>;
  startEventDemo: (scenario: string) => Promise<void>;
  toggleEventDemo: () => void;
}

const JunctionContext = createContext<JunctionContextValue | null>(null);

function notifySourceChanged() {
  window.dispatchEvent(new Event("trafficops:reset-live"));
}

export function JunctionProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const [selectedJunctionId, setSelectedJunctionId] = useState("north");
  const [selectedCameraId, setSelectedCameraId] = useState("north-cam-01");
  const [sourceMode, setSourceModeState] = useState<SourceMode>("live");
  const [scenarioFilter, setScenarioFilter] = useState("all");
  const [streamVersion, setStreamVersion] = useState(0);
  const [eventDemoOpen, setEventDemoOpen] = useState(false);
  const [unavailableReason, setUnavailableReason] = useState<string | null>(null);
  const [manualVideoId, setManualVideoId] = useState<string | null>(null);

  const junctionsQuery = useQuery({ queryKey: ["junctions"], queryFn: api.getJunctions, refetchInterval: 30_000 });
  const junctions = junctionsQuery.data?.items ?? [];
  const scenariosQuery = useQuery({ queryKey: ["demo-scenarios"], queryFn: api.getDemoScenarios, staleTime: Infinity });
  const scenarios = scenariosQuery.data?.items ?? [];

  const demoVideosQuery = useQuery({
    queryKey: ["demo-videos", selectedJunctionId],
    queryFn: () => api.getDemoVideos({ junctionId: selectedJunctionId }),
    refetchInterval: 20_000,
  });
  const allDemoVideos = demoVideosQuery.data?.items ?? [];

  const demoStatusQuery = useQuery({
    queryKey: ["demo-status"],
    queryFn: api.getDemoStatus,
    refetchInterval: 5_000,
  });
  const demoStatus = demoStatusQuery.data ?? null;

  const camerasQuery = useQuery({
    queryKey: ["junction-cameras", selectedJunctionId],
    queryFn: () => api.getJunctionCameras(selectedJunctionId),
  });
  const cameras = camerasQuery.data?.items ?? [];

  const selectedJunction = junctions.find((junction) => junction.id === selectedJunctionId) ?? junctions[0] ?? null;
  const effectiveJunctionId = selectedJunction?.id ?? selectedJunctionId;
  const junctionCameras = effectiveJunctionId ? cameras.filter((camera) => camera.junctionId === effectiveJunctionId) : [];
  const selectedCamera = junctionCameras.find((camera) => camera.id === selectedCameraId) ?? junctionCameras[0] ?? null;

  const filteredDemoVideos = useMemo(() => {
    const byScenario = scenarioFilter === "all"
      ? allDemoVideos
      : allDemoVideos.filter((video) => video.scenario === scenarioFilter);
    return [...byScenario].sort((a, b) => Number(b.available) - Number(a.available) || a.title.localeCompare(b.title));
  }, [allDemoVideos, scenarioFilter]);

  const selectedDemoVideo = useMemo(() => {
    if (manualVideoId) return filteredDemoVideos.find((video) => video.id === manualVideoId) ?? null;
    return filteredDemoVideos[0] ?? null;
  }, [manualVideoId, filteredDemoVideos]);

  const invalidateSession = useCallback(() => {
    client.invalidateQueries({ queryKey: ["summary"] });
    client.invalidateQueries({ queryKey: ["analytics"] });
    client.invalidateQueries({ queryKey: ["vehicles"] });
    client.invalidateQueries({ queryKey: ["plates"] });
    client.invalidateQueries({ queryKey: ["violations"] });
    client.invalidateQueries({ queryKey: ["violation-summary"] });
    client.invalidateQueries({ queryKey: ["alerts"] });
    client.invalidateQueries({ queryKey: ["alert-summary"] });
  }, [client]);

  const bumpSource = useCallback(() => {
    notifySourceChanged();
    invalidateSession();
    setStreamVersion((value) => value + 1);
  }, [invalidateSession]);

  const selectCamera = useCallback((cameraId: string) => {
    setSelectedCameraId(cameraId);
    setUnavailableReason(null);
  }, []);

  const launchDemo = useCallback(async (video: DemoVideo | null, cameraId: string) => {
    if (!video) {
      setUnavailableReason("No demo videos configured for this junction");
      return false;
    }
    if (!video.available) {
      setUnavailableReason("Demo video unavailable");
      setManualVideoId(video.id);
      bumpSource();
      return false;
    }
    setManualVideoId(video.id);
    setUnavailableReason(null);
    setSourceModeState("demo");
    setEventDemoOpen(false);
    try {
      const response = await api.startDemo(video.junctionId, cameraId, video.id);
      if (!response.available) {
        setUnavailableReason(response.reason ?? "Demo video unavailable");
      } else if (!response.started) {
        setUnavailableReason(response.reason ?? "Demo video could not be started");
      }
    } catch (reason) {
      setUnavailableReason(reason instanceof Error ? reason.message : "Demo video unavailable");
    }
    bumpSource();
    return true;
  }, [bumpSource]);

  const startDemo = useCallback(async (videoId?: string, cameraOverride?: string) => {
    const video = videoId ? filteredDemoVideos.find((item) => item.id === videoId) ?? null : selectedDemoVideo;
    return launchDemo(video, cameraOverride ?? video?.cameraId ?? selectedCamera?.id ?? "");
  }, [filteredDemoVideos, selectedDemoVideo, selectedCamera, launchDemo]);

  const stopDemo = useCallback(async () => {
    setManualVideoId(null);
    setUnavailableReason(null);
    setSourceModeState("live");
    try {
      await api.stopDemo();
    } catch {
      // Pipeline may already be unavailable; the live source is still restored.
    }
    client.invalidateQueries({ queryKey: ["demo-status"] });
    bumpSource();
  }, [client, bumpSource]);

  const selectJunction = useCallback(async (junctionId: string) => {
    if (junctionId === selectedJunctionId) return;
    setSelectedJunctionId(junctionId);
    setSelectedCameraId("");
    setUnavailableReason(null);
    if (sourceMode !== "demo" && !demoStatus?.active) return;
    let videos: DemoVideo[] = [];
    let cameras: CameraConfig[] = [];
    try {
      const [videosResult, camerasResult] = await Promise.all([
        client.fetchQuery<{ items: DemoVideo[] }>({
          queryKey: ["demo-videos", junctionId],
          queryFn: () => api.getDemoVideos({ junctionId }),
          staleTime: 20_000,
        }),
        client.fetchQuery<{ items: CameraConfig[] }>({
          queryKey: ["junction-cameras", junctionId],
          queryFn: () => api.getJunctionCameras(junctionId),
          staleTime: 20_000,
        }),
      ]);
      videos = videosResult.items;
      cameras = camerasResult.items;
    } catch {
      // Demo data lookup failed; the live source is restored below.
    }
    const candidates = scenarioFilter === "all"
      ? videos
      : videos.filter((video) => video.scenario === scenarioFilter);
    const first = candidates.find((video) => video.available) ?? candidates[0] ?? null;
    if (first) {
      void launchDemo(first, first.cameraId ?? cameras[0]?.id ?? "");
    } else {
      void stopDemo();
    }
  }, [selectedJunctionId, sourceMode, scenarioFilter, client, demoStatus, launchDemo, stopDemo]);

  const setSourceMode = useCallback((mode: SourceMode) => {
    setSourceModeState(mode);
    setUnavailableReason(null);
    if (mode === "demo") {
      void launchDemo(selectedDemoVideo, selectedDemoVideo?.cameraId ?? selectedCamera?.id ?? "");
    } else {
      void stopDemo();
    }
  }, [selectedDemoVideo, selectedCamera, launchDemo, stopDemo]);

  const pauseDemo = useCallback(async () => {
    try { await api.pauseDemo(); } catch { /* not playing */ }
    client.invalidateQueries({ queryKey: ["demo-status"] });
  }, [client]);

  const resumeDemo = useCallback(async () => {
    try { await api.resumeDemo(); } catch { /* not playing */ }
    client.invalidateQueries({ queryKey: ["demo-status"] });
  }, [client]);

  const restartDemo = useCallback(async () => {
    try { await api.restartDemo(); } catch { /* not playing */ }
    client.invalidateQueries({ queryKey: ["demo-status"] });
  }, [client]);

  const startEventDemo = useCallback(async (scenario: string) => {
    setScenarioFilter("all");
    const candidates = scenario === "all"
      ? allDemoVideos
      : allDemoVideos.filter((video) => video.scenario === scenario);
    const video = candidates.find((item) => item.available) ?? candidates[0] ?? null;
    if (!video) {
      setUnavailableReason("No demo video available for this scenario");
      return;
    }
    await startDemo(video.id);
  }, [allDemoVideos, startDemo]);

  const toggleEventDemo = useCallback(() => {
    setEventDemoOpen((open) => !open);
    setUnavailableReason(null);
  }, []);

  const value: JunctionContextValue = {
    junctions,
    junctionCameras,
    selectedJunction,
    selectedCamera,
    selectedJunctionId: effectiveJunctionId,
    selectedCameraId: selectedCamera?.id ?? "",
    sourceMode: demoStatus?.active ? "demo" : sourceMode,
    demoVideos: filteredDemoVideos,
    selectedDemoVideo,
    scenarioFilter,
    scenarios,
    demoStatus,
    streamVersion,
    eventDemoOpen,
    unavailableReason,
    selectJunction,
    selectCamera,
    setSourceMode,
    setScenarioFilter,
    startDemo,
    stopDemo,
    pauseDemo,
    resumeDemo,
    restartDemo,
    startEventDemo,
    toggleEventDemo,
  };

  return <JunctionContext.Provider value={value}>{children}</JunctionContext.Provider>;
}

export function useJunctions() {
  const value = useContext(JunctionContext);
  if (!value) throw new Error("useJunctions must be used within JunctionProvider");
  return value;
}
