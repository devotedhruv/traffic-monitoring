import { useQuery } from "@tanstack/react-query";
import {
  BellRing, Bot, Camera, CheckCircle2, ChevronRight, Database, HeartPulse, Search,
  Settings2, Shield, ShieldAlert, TriangleAlert, UserRound, Users, Webhook
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../app/AuthContext";
import { useLanguage } from "../app/LanguageContext";
import { PageHeader } from "../components/ui/PageHeader";
import { SettingsSection } from "../features/settings/SettingsSections";
import { settingsStorage, validateSettings } from "../features/settings/settingsStorage";
import { createDefaultSettings, sectionCatalog, type ManagedCamera, type SettingsSectionId, type TrafficOpsSettings } from "../features/settings/types";
import { cx } from "../lib/format";
import { api } from "../services/api";

const icons = {
  general: Settings2,
  cameras: Camera,
  detection: Bot,
  alerts: BellRing,
  users: Users,
  recording: Database,
  integrations: Webhook,
  privacy: Shield,
  health: HeartPulse,
  account: UserRound,
  danger: ShieldAlert
} as const;

function cloneSettings(settings: TrafficOpsSettings) {
  return structuredClone(settings);
}

export function SettingsPage() {
  const { language, setLanguage } = useLanguage();
  const { user } = useAuth();
  const [hadSavedSettings] = useState(() => settingsStorage.hasSavedSettings());
  const [initialSettings] = useState(() => {
    const loaded = settingsStorage.load("light");
    if (!hadSavedSettings) loaded.general.language = language;
    if (!hadSavedSettings && user) loaded.account = { ...loaded.account, name: user.name, email: user.email };
    return loaded;
  });
  const [saved, setSaved] = useState<TrafficOpsSettings>(() => cloneSettings(initialSettings));
  const [draft, setDraft] = useState<TrafficOpsSettings>(() => cloneSettings(initialSettings));
  const [activeSection, setActiveSection] = useState<SettingsSectionId>("general");
  const [search, setSearch] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const seededCameras = useRef(hadSavedSettings);
  const cameras = useQuery({ queryKey: ["cameras"], queryFn: api.getCameras });
  const health = useQuery({ queryKey: ["system-health"], queryFn: api.getHealth, refetchInterval: 30_000 });

  useEffect(() => {
    setSaved((current) => current.general.language === language ? current : { ...current, general: { ...current.general, language } });
    setDraft((current) => current.general.language === language ? current : { ...current, general: { ...current.general, language } });
  }, [language]);

  useEffect(() => {
    if (seededCameras.current || !cameras.data) return;
    seededCameras.current = true;
    const cameraSettings: ManagedCamera[] = cameras.data.map((camera) => ({
      id: camera.id,
      name: camera.name,
      junction: camera.name,
      streamUrl: "",
      resolution: "1920x1080",
      fps: 25,
      enabled: camera.streamAvailable
    }));
    setSaved((current) => ({ ...current, cameras: cameraSettings }));
    setDraft((current) => ({ ...current, cameras: cameraSettings }));
  }, [cameras.data]);

  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(saved), [draft, saved]);
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    const beforeNavigate = (event: Event) => {
      if (dirty && !window.confirm("You have unsaved Settings changes. Leave without saving?")) event.preventDefault();
    };
    window.addEventListener("beforeunload", beforeUnload);
    window.addEventListener("trafficops:before-navigate", beforeNavigate);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      window.removeEventListener("trafficops:before-navigate", beforeNavigate);
    };
  }, [dirty]);

  const normalizedSearch = search.trim().toLowerCase();
  const matchingSections = useMemo(() => sectionCatalog.filter((section) => !normalizedSearch || `${section.label} ${section.description} ${section.keywords}`.toLowerCase().includes(normalizedSearch)), [normalizedSearch]);
  const visibleSection = matchingSections.some((section) => section.id === activeSection) ? activeSection : matchingSections[0]?.id;
  const activeMeta = sectionCatalog.find((section) => section.id === visibleSection);

  const save = () => {
    const nextErrors = validateSettings(draft);
    if (nextErrors.length) {
      setErrors(nextErrors);
      setMessage("");
      return;
    }
    try {
      settingsStorage.save(draft);
      setSaved(cloneSettings(draft));
      setLanguage(draft.general.language);
      setErrors([]);
      setMessage("Settings saved on this device.");
      window.dispatchEvent(new CustomEvent("trafficops:settings-updated", { detail: draft }));
    } catch {
      setErrors(["Settings could not be saved. Browser storage may be unavailable or full."]);
      setMessage("");
    }
  };

  const discard = () => {
    setDraft(cloneSettings(saved));
    setErrors([]);
    setMessage("Unsaved changes discarded.");
  };

  const reset = () => {
    settingsStorage.reset();
    const defaults = createDefaultSettings("light");
    defaults.general.language = "en";
    if (user) defaults.account = { ...defaults.account, name: user.name, email: user.email };
    if (cameras.data) defaults.cameras = cameras.data.map((camera) => ({ id: camera.id, name: camera.name, junction: camera.name, streamUrl: "", resolution: "1920x1080", fps: 25, enabled: camera.streamAvailable }));
    setSaved(cloneSettings(defaults));
    setDraft(cloneSettings(defaults));
    setLanguage("en");
    setErrors([]);
    setMessage("Local settings were reset to defaults.");
  };

  return <div className="space-y-5 pb-24">
    <PageHeader eyebrow="Administration  ›  Settings" title="Settings" subtitle="Manage system preferences, cameras, detection rules and security." action={dirty ? <span className="inline-flex items-center gap-2 rounded-full border border-warning/25 bg-warning/10 px-3 py-1.5 text-[10px] font-bold text-warning"><span className="h-1.5 w-1.5 rounded-full bg-warning" />Unsaved changes</span> : <span className="inline-flex items-center gap-2 rounded-full border border-success/20 bg-success/10 px-3 py-1.5 text-[10px] font-bold text-success"><CheckCircle2 size={13} />Up to date</span>} />

    <div className="relative"><Search className="pointer-events-none absolute left-3.5 top-3.5 text-muted" size={16} /><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} className="field pl-10" placeholder="Search settings, cameras, alerts, privacy…" aria-label="Search settings" />{normalizedSearch && <span className="absolute right-3 top-3.5 text-[10px] font-semibold text-muted">{matchingSections.length} {matchingSections.length === 1 ? "section" : "sections"}</span>}</div>

    {errors.length > 0 && <div role="alert" className="rounded-2xl border border-danger/25 bg-danger/5 p-4 text-danger"><div className="flex items-center gap-2 text-xs font-bold"><TriangleAlert size={16} />Check these settings</div><ul className="mt-2 list-disc space-y-1 pl-5 text-[10px] leading-5">{errors.map((error) => <li key={error}>{error}</li>)}</ul></div>}
    {message && <div role="status" className="flex items-center gap-2 rounded-xl border border-success/20 bg-success/5 px-3 py-2.5 text-[10px] font-semibold text-success"><CheckCircle2 size={14} />{message}</div>}

    <div className="lg:grid lg:grid-cols-[280px_minmax(0,1fr)] lg:items-start lg:gap-5">
      <aside className="hidden lg:sticky lg:top-[92px] lg:block"><nav className="rounded-2xl border border-border bg-card p-2 shadow-panel" aria-label="Settings categories">{matchingSections.map((section) => { const Icon = icons[section.id]; const active = section.id === visibleSection; return <button key={section.id} type="button" onClick={() => { setActiveSection(section.id); setMessage(""); }} className={cx("flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left", active ? "bg-primary-soft text-primary" : "text-secondary hover:bg-elevated hover:text-ink")}><span className={cx("grid h-8 w-8 shrink-0 place-items-center rounded-lg", active ? "bg-primary/10" : "bg-elevated")}><Icon size={15} /></span><span className="min-w-0 flex-1"><strong className="block truncate text-[11px]">{section.label}</strong><span className="mt-0.5 block truncate text-[9px] text-muted">{section.description}</span></span><ChevronRight size={14} className={active ? "opacity-100" : "opacity-30"} /></button>; })}{matchingSections.length === 0 && <p className="px-3 py-8 text-center text-[10px] text-muted">No settings match “{search}”.</p>}</nav></aside>

      <div className="space-y-4">
        <label className="block lg:hidden"><span className="mb-1.5 block text-[10px] font-bold text-secondary">Settings category</span><select className="field" value={visibleSection ?? ""} onChange={(event) => setActiveSection(event.target.value as SettingsSectionId)} disabled={matchingSections.length === 0}>{matchingSections.map((section) => <option key={section.id} value={section.id}>{section.label}</option>)}</select></label>
        {visibleSection && activeMeta ? <><div className="rounded-xl border border-border bg-surface-secondary/35 px-4 py-3"><p className="text-xs font-bold">{activeMeta.label}</p><p className="mt-1 text-[10px] text-muted">{activeMeta.description}</p></div><SettingsSection section={visibleSection} settings={draft} onChange={(next) => { setDraft(next); setErrors([]); setMessage(""); }} health={health.data} healthLoading={health.isLoading || health.isFetching} healthError={health.isError} onRefreshHealth={() => { void health.refetch(); }} onReset={reset} /></> : <div className="grid min-h-56 place-items-center rounded-2xl border border-dashed border-border bg-card p-6 text-center"><div><Search className="mx-auto text-muted" /><p className="mt-3 text-sm font-bold">No matching settings</p><button type="button" className="secondary-button mt-3" onClick={() => setSearch("")}>Clear search</button></div></div>}
      </div>
    </div>

    <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-header/95 p-3 shadow-[0_-8px_24px_rgb(0_0_0/0.08)] backdrop-blur-xl lg:left-[var(--trafficops-sidebar-width)]"><div className="mx-auto flex max-w-[1640px] items-center justify-between gap-3"><div className="hidden sm:block"><p className="text-[10px] font-bold">{dirty ? "You have unsaved changes" : "All changes saved"}</p><p className="mt-0.5 text-[9px] text-muted">Only non-sensitive preferences are stored in this browser.</p></div><div className="ml-auto flex gap-2"><button type="button" className="secondary-button h-11 px-4" disabled={!dirty} onClick={discard}>Discard changes</button><button type="button" className="primary-button h-11 px-5" disabled={!dirty} onClick={save}>Save changes</button></div></div></div>
  </div>;
}
