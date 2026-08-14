import {
  Activity, BellRing, Bot, Camera, CircleGauge, Database, Download, ExternalLink, HardDrive,
  HeartPulse, KeyRound, LockKeyhole, MapPinned, Plus, Radio, RefreshCw, Save, Settings2,
  Shield, ShieldAlert, Trash2, UserCog, UserRound, Users, Video, Webhook
} from "lucide-react";
import { useState } from "react";
import type { SystemHealth } from "../../types";
import {
  ConfirmDialog, FieldLabel, Notice, SelectField, SettingRow, SettingsGroup, StatusPill,
  TextField, Toggle, ToggleGrid
} from "./SettingsControls";
import type { ManagedCamera, ManagedUser, SettingsSectionId, TrafficOpsSettings } from "./types";

interface SectionProps {
  settings: TrafficOpsSettings;
  onChange: (settings: TrafficOpsSettings) => void;
}

function GeneralSection({ settings, onChange }: SectionProps) {
  const update = (patch: Partial<TrafficOpsSettings["general"]>) => onChange({ ...settings, general: { ...settings.general, ...patch } });
  return <SettingsGroup icon={Settings2} title="General settings" description="Choose how this SadakDrishti workspace refreshes and displays local information.">
    <SettingRow title="Workspace identity" description="Displayed in Settings and future generated exports."><TextField label="System / site name" value={settings.general.systemName} maxLength={80} onChange={(event) => update({ systemName: event.target.value })} /></SettingRow>
    <SettingRow title="Language and timezone" description="Timezone is used for operator-facing timestamps. Stored evidence timestamps remain unchanged."><div className="grid gap-3 sm:grid-cols-2"><SelectField label="Language" value={settings.general.language} onChange={(event) => update({ language: event.target.value as TrafficOpsSettings["general"]["language"] })}><option value="en">English</option><option value="ne">नेपाली</option></SelectField><SelectField label="Timezone" value={settings.general.timezone} onChange={(event) => update({ timezone: event.target.value })}><option value="Asia/Kathmandu">Asia/Kathmandu</option><option value="Asia/Kolkata">Asia/Kolkata</option><option value="UTC">UTC</option><option value="Asia/Dubai">Asia/Dubai</option></SelectField></div></SettingRow>
    <SettingRow title="Date and time format"><div className="grid gap-3 sm:grid-cols-2"><SelectField label="Date format" value={settings.general.dateFormat} onChange={(event) => update({ dateFormat: event.target.value as TrafficOpsSettings["general"]["dateFormat"] })}><option>MMM d, yyyy</option><option>dd/MM/yyyy</option><option>yyyy-MM-dd</option></SelectField><SelectField label="Clock" value={settings.general.timeFormat} onChange={(event) => update({ timeFormat: event.target.value as "12h" | "24h" })}><option value="12h">12-hour</option><option value="24h">24-hour</option></SelectField></div></SettingRow>
    <SettingRow title="Dashboard refresh interval" description="Allowed range: 5–300 seconds."><TextField label="Refresh every" hint="seconds" type="number" min={5} max={300} value={settings.general.refreshInterval} onChange={(event) => update({ refreshInterval: Number(event.target.value) })} /></SettingRow>
  </SettingsGroup>;
}

const emptyCamera = (): ManagedCamera => ({ id: `camera-${Date.now()}`, name: "", junction: "", streamUrl: "", resolution: "1920x1080", fps: 25, enabled: true });

function streamUrlIsSafe(value: string) {
  if (!value.trim()) return true;
  try {
    const url = new URL(value);
    return ["rtsp:", "rtsps:", "http:", "https:"].includes(url.protocol) && !url.username && !url.password;
  } catch {
    return false;
  }
}

function CamerasSection({ settings, onChange }: SectionProps) {
  const [editing, setEditing] = useState<ManagedCamera | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const saveCamera = () => {
    if (!editing) return;
    if (!editing.name.trim() || !editing.junction.trim()) return setMessage("Camera name and junction are required.");
    if (!streamUrlIsSafe(editing.streamUrl)) return setMessage("Use a valid RTSP or HTTP(S) URL without embedded credentials.");
    if (editing.fps < 1 || editing.fps > 120) return setMessage("FPS must be between 1 and 120.");
    const exists = settings.cameras.some((camera) => camera.id === editing.id);
    const cameras = exists ? settings.cameras.map((camera) => camera.id === editing.id ? editing : camera) : [...settings.cameras, editing];
    onChange({ ...settings, cameras });
    setEditing(null);
    setMessage(null);
  };
  const testConnection = () => {
    if (!editing?.streamUrl.trim()) return setMessage("Enter a stream URL before checking it.");
    setMessage(streamUrlIsSafe(editing.streamUrl) ? "URL format is valid. A live connection test requires a camera backend endpoint." : "The URL is invalid or contains embedded credentials.");
  };
  return <div className="space-y-4"><SettingsGroup icon={Camera} title="Cameras & junctions" description="Manage display metadata without changing the existing live-feed pipeline.">
    <SettingRow title="Configured sources" description="Secrets and RTSP credentials are never stored in the browser." stack>
      <div className="space-y-3">
        {settings.cameras.length === 0 && <div className="rounded-xl border border-dashed border-border p-6 text-center"><Camera className="mx-auto text-muted" size={24} /><p className="mt-2 text-xs font-bold">No local camera configuration</p><p className="mt-1 text-[10px] text-muted">Add metadata for a camera or junction. Existing live feeds remain untouched.</p></div>}
        {settings.cameras.map((camera) => <article key={camera.id} className="flex flex-col gap-3 rounded-xl border border-border bg-surface-secondary/35 p-3 sm:flex-row sm:items-center"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary"><Video size={17} /></span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h3 className="truncate text-xs font-bold">{camera.name}</h3><StatusPill tone={camera.enabled ? "success" : "neutral"}>{camera.enabled ? "Enabled" : "Disabled"}</StatusPill></div><p className="mt-1 truncate text-[10px] text-muted">{camera.junction} · {camera.resolution} · {camera.fps} FPS</p></div><div className="flex gap-2"><button type="button" className="secondary-button" onClick={() => { setEditing({ ...camera }); setMessage(null); }}>Edit</button><button type="button" className="icon-button h-10 w-10 text-danger" aria-label={`Delete ${camera.name}`} onClick={() => setDeleteId(camera.id)}><Trash2 size={14} /></button></div></article>)}
        <button type="button" className="secondary-button" onClick={() => { setEditing(emptyCamera()); setMessage(null); }}><Plus size={14} />Add camera</button>
      </div>
    </SettingRow>
  </SettingsGroup>
    {editing && <SettingsGroup icon={Radio} title={settings.cameras.some((camera) => camera.id === editing.id) ? "Edit camera" : "Add camera"} description="Configuration stays local until a camera-management backend is connected.">
      <SettingRow title="Source details" stack><div className="grid gap-3 sm:grid-cols-2"><TextField label="Camera name" value={editing.name} onChange={(event) => setEditing({ ...editing, name: event.target.value })} /><TextField label="Junction / location" value={editing.junction} onChange={(event) => setEditing({ ...editing, junction: event.target.value })} /><TextField label="RTSP or IP stream URL" hint="No credentials" placeholder="rtsp://camera.local/stream" value={editing.streamUrl} onChange={(event) => setEditing({ ...editing, streamUrl: event.target.value })} className="sm:col-span-2" /><SelectField label="Resolution" value={editing.resolution} onChange={(event) => setEditing({ ...editing, resolution: event.target.value as ManagedCamera["resolution"] })}><option>1280x720</option><option>1920x1080</option><option>2560x1440</option><option>3840x2160</option></SelectField><TextField label="Frames per second" type="number" min={1} max={120} value={editing.fps} onChange={(event) => setEditing({ ...editing, fps: Number(event.target.value) })} /></div><div className="mt-3 flex items-center justify-between rounded-xl border border-border bg-surface-secondary/35 px-3 py-2.5"><span className="text-[11px] font-bold">Camera enabled</span><Toggle checked={editing.enabled} onChange={(enabled) => setEditing({ ...editing, enabled })} label="Enable camera" /></div>{message && <div className="mt-3"><Notice tone={message.startsWith("URL format") ? "info" : "warning"}>{message}</Notice></div>}<div className="mt-4 flex flex-wrap justify-end gap-2"><button type="button" className="secondary-button" onClick={testConnection}><ExternalLink size={14} />Check URL</button><button type="button" className="secondary-button" onClick={() => { setEditing(null); setMessage(null); }}>Cancel</button><button type="button" className="primary-button h-10 px-4" onClick={saveCamera}><Save size={14} />Keep changes</button></div></SettingRow>
    </SettingsGroup>}
    <ConfirmDialog open={Boolean(deleteId)} title="Remove camera configuration?" description="This removes only the browser-stored settings entry. It does not delete an existing backend camera or recording." confirmLabel="Remove camera" danger onCancel={() => setDeleteId(null)} onConfirm={() => { onChange({ ...settings, cameras: settings.cameras.filter((camera) => camera.id !== deleteId) }); setDeleteId(null); }} />
  </div>;
}

function DetectionSection({ settings, onChange }: SectionProps) {
  const update = (patch: Partial<TrafficOpsSettings["detection"]>) => onChange({ ...settings, detection: { ...settings.detection, ...patch } });
  const setObject = (key: keyof TrafficOpsSettings["detection"]["objects"], checked: boolean) => update({ objects: { ...settings.detection.objects, [key]: checked } });
  const setViolation = (key: keyof TrafficOpsSettings["detection"]["violations"], checked: boolean) => update({ violations: { ...settings.detection.violations, [key]: checked } });
  return <SettingsGroup icon={Bot} title="AI detection" description="Set desired detection defaults. These preferences do not silently reconfigure the running model.">
    <SettingRow title="Detected objects" description="Choose the classes operators want visible in future configured pipelines." stack><ToggleGrid items={([
      ["car", "Cars"], ["bike", "Motorcycles & bikes"], ["bus", "Buses"], ["truck", "Trucks"], ["pedestrian", "Pedestrians"]
    ] as const).map(([key, label]) => ({ label, checked: settings.detection.objects[key], onChange: (checked) => setObject(key, checked) }))} /></SettingRow>
    <SettingRow title="Confidence threshold" description="Higher values reduce uncertain detections."><FieldLabel label={`${settings.detection.confidence}% confidence`}><input className="w-full accent-[rgb(var(--color-primary))]" type="range" min={1} max={100} value={settings.detection.confidence} onChange={(event) => update({ confidence: Number(event.target.value) })} /></FieldLabel></SettingRow>
    <SettingRow title="Default speed limit"><TextField label="Speed limit" hint="km/h" type="number" min={5} max={200} value={settings.detection.speedLimit} onChange={(event) => update({ speedLimit: Number(event.target.value) })} /></SettingRow>
    <SettingRow title="Violation rules" description="Availability still depends on model weights and junction calibration." stack><ToggleGrid items={([
      ["overspeed", "Overspeed"], ["redLight", "Red-light violation"], ["wrongLane", "Wrong-lane driving"], ["noHelmet", "No helmet"]
    ] as const).map(([key, label]) => ({ label, checked: settings.detection.violations[key], onChange: (checked) => setViolation(key, checked) }))} /></SettingRow>
    <SettingRow title="Number-plate recognition" description="Requires dedicated plate-detector weights and applicable privacy controls."><Toggle checked={settings.detection.plateRecognition} onChange={(plateRecognition) => update({ plateRecognition })} label="Toggle number-plate recognition" /></SettingRow>
    <SettingRow title="Junction-specific overrides" description="Prepare separate rule profiles per junction when a backend supports them."><Toggle checked={settings.detection.junctionOverrides} onChange={(junctionOverrides) => update({ junctionOverrides })} label="Toggle junction overrides" /></SettingRow>
  </SettingsGroup>;
}

function AlertsSection({ settings, onChange }: SectionProps) {
  const update = (patch: Partial<TrafficOpsSettings["alerts"]>) => onChange({ ...settings, alerts: { ...settings.alerts, ...patch } });
  const setType = (key: keyof TrafficOpsSettings["alerts"]["alertTypes"], checked: boolean) => update({ alertTypes: { ...settings.alerts.alertTypes, [key]: checked } });
  return <SettingsGroup icon={BellRing} title="Alerts & notifications" description="Control operator-facing preferences. External delivery still requires a configured provider.">
    <SettingRow title="Alert types" stack><ToggleGrid items={([
      ["violation", "Traffic violations"], ["cameraOffline", "Camera offline"], ["systemHealth", "System health"]
    ] as const).map(([key, label]) => ({ label, checked: settings.alerts.alertTypes[key], onChange: (checked) => setType(key, checked) }))} /></SettingRow>
    <SettingRow title="Minimum alert severity"><SelectField label="Notify from" value={settings.alerts.minimumSeverity} onChange={(event) => update({ minimumSeverity: event.target.value as TrafficOpsSettings["alerts"]["minimumSeverity"] })}><option>Low</option><option>Medium</option><option>High</option><option>Critical</option></SelectField></SettingRow>
    <SettingRow title="Delivery channels" description="Email and SMS require provider configuration." stack><ToggleGrid items={[{ label: "Email", checked: settings.alerts.email, onChange: (email) => update({ email }) }, { label: "SMS", checked: settings.alerts.sms, onChange: (sms) => update({ sms }) }, { label: "In-app / push", checked: settings.alerts.push, onChange: (push) => update({ push }) }]} /></SettingRow>
    <SettingRow title="Quiet hours" description="Critical alerts may still be shown in the app." stack><div className="flex items-center justify-between rounded-xl border border-border bg-surface-secondary/35 px-3 py-2.5"><span className="text-[11px] font-bold">Enable quiet hours</span><Toggle checked={settings.alerts.quietHoursEnabled} onChange={(quietHoursEnabled) => update({ quietHoursEnabled })} label="Enable quiet hours" /></div><div className="mt-3 grid gap-3 sm:grid-cols-2"><TextField label="From" type="time" disabled={!settings.alerts.quietHoursEnabled} value={settings.alerts.quietFrom} onChange={(event) => update({ quietFrom: event.target.value })} /><TextField label="To" type="time" disabled={!settings.alerts.quietHoursEnabled} value={settings.alerts.quietTo} onChange={(event) => update({ quietTo: event.target.value })} /></div></SettingRow>
    <SettingRow title="Alert cooldown"><TextField label="Cooldown" hint="minutes" type="number" min={0} max={1440} value={settings.alerts.cooldownMinutes} onChange={(event) => update({ cooldownMinutes: Number(event.target.value) })} /></SettingRow>
    <SettingRow title="Emergency contact" stack><div className="grid gap-3 sm:grid-cols-2"><TextField label="Contact name" value={settings.alerts.emergencyContactName} onChange={(event) => update({ emergencyContactName: event.target.value })} /><TextField label="Phone number" type="tel" value={settings.alerts.emergencyContactPhone} onChange={(event) => update({ emergencyContactPhone: event.target.value })} /></div></SettingRow>
  </SettingsGroup>;
}

const emptyUser = (): ManagedUser => ({ id: `user-${Date.now()}`, name: "", email: "", role: "Viewer", status: "Active", junctionAccess: [] });

function UsersSection({ settings, onChange }: SectionProps) {
  const [editing, setEditing] = useState<ManagedUser | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const saveUser = () => {
    if (!editing) return;
    if (!editing.name.trim() || !/^\S+@\S+\.\S+$/.test(editing.email)) return setError("Enter a name and valid email address.");
    const users = settings.users.some((user) => user.id === editing.id) ? settings.users.map((user) => user.id === editing.id ? editing : user) : [...settings.users, editing];
    onChange({ ...settings, users }); setEditing(null); setError("");
  };
  return <div className="space-y-4"><SettingsGroup icon={Users} title="Users & permissions" description="Plan operator access locally. Authentication and authorization remain backend-controlled.">
    <SettingRow title="Workspace users" description="Changing these entries does not create or revoke real login accounts." stack><Notice tone="warning">User and role changes are interface preferences until a secure administration API is connected.</Notice><div className="mt-3 space-y-2">{settings.users.map((user) => <article key={user.id} className="flex flex-col gap-3 rounded-xl border border-border bg-surface-secondary/35 p-3 sm:flex-row sm:items-center"><span className="grid h-9 w-9 place-items-center rounded-full bg-primary-soft text-primary"><UserRound size={16} /></span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h3 className="truncate text-xs font-bold">{user.name}</h3><StatusPill tone={user.status === "Active" ? "success" : "warning"}>{user.status}</StatusPill><StatusPill>{user.role}</StatusPill></div><p className="mt-1 truncate text-[10px] text-muted">{user.email} · {user.junctionAccess.length ? user.junctionAccess.join(", ") : "All junctions"}</p></div><div className="flex gap-2"><button type="button" className="secondary-button" onClick={() => setEditing({ ...user })}>Edit</button><button type="button" className="icon-button h-10 w-10 text-danger" onClick={() => setDeleteId(user.id)} aria-label={`Remove ${user.name}`}><Trash2 size={14} /></button></div></article>)}{settings.users.length === 0 && <p className="rounded-xl border border-dashed border-border p-4 text-center text-[10px] text-muted">No locally managed users.</p>}</div><button type="button" className="secondary-button mt-3" onClick={() => { setEditing(emptyUser()); setError(""); }}><Plus size={14} />Add user</button></SettingRow>
  </SettingsGroup>
    {editing && <SettingsGroup icon={UserCog} title={settings.users.some((user) => user.id === editing.id) ? "Edit user" : "Add user"} description="Define the intended role and junction access."><SettingRow title="User details" stack><div className="grid gap-3 sm:grid-cols-2"><TextField label="Full name" value={editing.name} onChange={(event) => setEditing({ ...editing, name: event.target.value })} /><TextField label="Email" type="email" value={editing.email} onChange={(event) => setEditing({ ...editing, email: event.target.value })} /><SelectField label="Role" value={editing.role} onChange={(event) => setEditing({ ...editing, role: event.target.value as ManagedUser["role"] })}><option>Admin</option><option>Operator</option><option>Viewer</option></SelectField><SelectField label="Account status" value={editing.status} onChange={(event) => setEditing({ ...editing, status: event.target.value as ManagedUser["status"] })}><option>Active</option><option>Suspended</option></SelectField><TextField className="sm:col-span-2" label="Junction access" hint="Comma-separated; blank means all" value={editing.junctionAccess.join(", ")} onChange={(event) => setEditing({ ...editing, junctionAccess: event.target.value.split(",").map((value) => value.trim()).filter(Boolean) })} /></div>{error && <div className="mt-3"><Notice tone="danger">{error}</Notice></div>}<div className="mt-4 flex justify-end gap-2"><button type="button" className="secondary-button" onClick={() => setEditing(null)}>Cancel</button><button type="button" className="primary-button h-10 px-4" onClick={saveUser}><Save size={14} />Keep changes</button></div></SettingRow></SettingsGroup>}
    <ConfirmDialog open={Boolean(deleteId)} title="Remove user entry?" description="This removes the local settings entry only. It does not revoke a real login account." confirmLabel="Remove entry" danger onCancel={() => setDeleteId(null)} onConfirm={() => { onChange({ ...settings, users: settings.users.filter((user) => user.id !== deleteId) }); setDeleteId(null); }} />
  </div>;
}

function RecordingSection({ settings, onChange }: SectionProps) {
  const update = (patch: Partial<TrafficOpsSettings["recording"]>) => onChange({ ...settings, recording: { ...settings.recording, ...patch } });
  return <SettingsGroup icon={Database} title="Recording & data" description="Set desired retention and export behavior for evidence workflows.">
    <SettingRow title="Storage usage" description="CPU, disk and recording telemetry are not exposed by the current backend."><div className="rounded-xl border border-border bg-surface-secondary/35 p-3"><div className="flex items-center gap-2 text-[11px] font-bold"><HardDrive size={15} className="text-muted" />Usage unavailable</div><p className="mt-1 text-[9px] text-muted">Connect storage telemetry to display capacity.</p></div></SettingRow>
    <SettingRow title="Recording retention"><TextField label="Retention period" hint="days" type="number" min={1} max={3650} value={settings.recording.retentionDays} onChange={(event) => update({ retentionDays: Number(event.target.value) })} /></SettingRow>
    <SettingRow title="Evidence clip duration"><TextField label="Clip length" hint="seconds" type="number" min={5} max={300} value={settings.recording.evidenceClipSeconds} onChange={(event) => update({ evidenceClipSeconds: Number(event.target.value) })} /></SettingRow>
    <SettingRow title="Automatic cleanup" description="Requires backend support before recordings can be removed."><Toggle checked={settings.recording.autoCleanup} onChange={(autoCleanup) => update({ autoCleanup })} label="Toggle automatic cleanup" /></SettingRow>
    <SettingRow title="Export and backup"><div className="grid gap-3 sm:grid-cols-2"><SelectField label="Video export format" value={settings.recording.exportFormat} onChange={(event) => update({ exportFormat: event.target.value as TrafficOpsSettings["recording"]["exportFormat"] })}><option>MP4</option><option>AVI</option><option>WebM</option></SelectField><SelectField label="Backup frequency" value={settings.recording.backupFrequency} onChange={(event) => update({ backupFrequency: event.target.value as TrafficOpsSettings["recording"]["backupFrequency"] })}><option>Never</option><option>Daily</option><option>Weekly</option><option>Monthly</option></SelectField></div></SettingRow>
  </SettingsGroup>;
}

function IntegrationsSection({ settings, onChange }: SectionProps) {
  const [testMessage, setTestMessage] = useState("");
  const update = (patch: Partial<TrafficOpsSettings["integrations"]>) => onChange({ ...settings, integrations: { ...settings.integrations, ...patch } });
  const checkWebhook = () => {
    try { const url = new URL(settings.integrations.webhookUrl); setTestMessage(["http:", "https:"].includes(url.protocol) && !url.username && !url.password ? "Webhook URL format is valid. No network request was sent." : "Use an HTTP(S) URL without embedded credentials."); }
    catch { setTestMessage("Enter a valid webhook URL."); }
  };
  return <SettingsGroup icon={Webhook} title="Integrations" description="Prepare connections without storing tokens, passwords or API keys in the browser.">
    <SettingRow title="Traffic police integration" description="A secure server-side API connector is required."><div className="flex items-center justify-end gap-3"><StatusPill tone="warning">Backend required</StatusPill><Toggle checked={settings.integrations.trafficPoliceEnabled} onChange={(trafficPoliceEnabled) => update({ trafficPoliceEnabled })} label="Enable traffic police integration preference" /></div></SettingRow>
    <SettingRow title="Webhook" description="Only the endpoint is stored. Secrets must be managed server-side." stack><div className="flex flex-col gap-2 sm:flex-row"><div className="flex-1"><TextField label="Webhook URL" type="url" placeholder="https://example.com/traffic-events" value={settings.integrations.webhookUrl} onChange={(event) => { update({ webhookUrl: event.target.value }); setTestMessage(""); }} /></div><button type="button" className="secondary-button self-end" onClick={checkWebhook}>Check URL</button></div>{testMessage && <div className="mt-3"><Notice tone={testMessage.startsWith("Webhook") ? "info" : "warning"}>{testMessage}</Notice></div>}</SettingRow>
    <SettingRow title="Messaging providers"><div className="grid gap-3 sm:grid-cols-2"><SelectField label="Email provider" value={settings.integrations.emailProvider} onChange={(event) => update({ emailProvider: event.target.value as TrafficOpsSettings["integrations"]["emailProvider"] })}><option>Not configured</option><option>SMTP</option><option>SendGrid</option><option>Mailgun</option></SelectField><SelectField label="SMS provider" value={settings.integrations.smsProvider} onChange={(event) => update({ smsProvider: event.target.value as TrafficOpsSettings["integrations"]["smsProvider"] })}><option>Not configured</option><option>Twilio</option><option>Sparrow SMS</option><option>Custom</option></SelectField></div></SettingRow>
    <SettingRow title="Map and GPS"><div className="grid gap-3 sm:grid-cols-2"><SelectField label="Map provider" value={settings.integrations.mapProvider} onChange={(event) => update({ mapProvider: event.target.value as TrafficOpsSettings["integrations"]["mapProvider"] })}><option>OpenStreetMap</option><option>Google Maps</option><option>Mapbox</option></SelectField><div className="flex items-end"><div className="flex h-11 w-full items-center justify-between rounded-xl border border-border bg-surface px-3"><span className="flex items-center gap-2 text-[11px] font-bold"><MapPinned size={15} />GPS enrichment</span><Toggle checked={settings.integrations.gpsEnabled} onChange={(gpsEnabled) => update({ gpsEnabled })} label="Toggle GPS enrichment" /></div></div></div></SettingRow>
  </SettingsGroup>;
}

function PrivacySection({ settings, onChange }: SectionProps) {
  const update = (patch: Partial<TrafficOpsSettings["privacy"]>) => onChange({ ...settings, privacy: { ...settings.privacy, ...patch } });
  return <SettingsGroup icon={Shield} title="Privacy & security" description="Privacy preferences complement, but do not replace, server-side enforcement and policy.">
    <SettingRow title="Anonymisation" stack><ToggleGrid items={[{ label: "Blur detected faces", description: "Requires a face-blurring pipeline", checked: settings.privacy.blurFaces, onChange: (blurFaces) => update({ blurFaces }) }, { label: "Blur number plates", description: "Affects intended exports and previews", checked: settings.privacy.blurPlates, onChange: (blurPlates) => update({ blurPlates }) }]} /></SettingRow>
    <SettingRow title="Session timeout"><TextField label="Automatic timeout" hint="minutes" type="number" min={5} max={1440} value={settings.privacy.sessionTimeoutMinutes} onChange={(event) => update({ sessionTimeoutMinutes: Number(event.target.value) })} /></SettingRow>
    <SettingRow title="Two-factor authentication" description="Preference only until an identity provider supports enrollment."><div className="flex items-center justify-end gap-3"><StatusPill tone="warning">Backend required</StatusPill><Toggle checked={settings.privacy.twoFactorPreferred} onChange={(twoFactorPreferred) => update({ twoFactorPreferred })} label="Prefer two-factor authentication" /></div></SettingRow>
    <SettingRow title="Audit logging" description="Record intended administrative actions when server-side audit storage is connected."><Toggle checked={settings.privacy.auditLogging} onChange={(auditLogging) => update({ auditLogging })} label="Toggle audit logging" /></SettingRow>
    <SettingRow title="Unknown devices" description="Require explicit review of new operator devices."><Toggle checked={settings.privacy.restrictUnknownDevices} onChange={(restrictUnknownDevices) => update({ restrictUnknownDevices })} label="Restrict unknown devices" /></SettingRow>
  </SettingsGroup>;
}

function SystemHealthSection({ health, loading, error, onRefresh }: { health?: SystemHealth; loading: boolean; error: boolean; onRefresh: () => void }) {
  const downloadDiagnostics = () => {
    const payload = JSON.stringify({ generatedAt: new Date().toISOString(), source: health ? "GET /api/health" : "unavailable", health: health ?? null }, null, 2);
    const url = URL.createObjectURL(new Blob([payload], { type: "application/json" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `trafficops-diagnostics-${new Date().toISOString().slice(0, 10)}.json`; anchor.click(); URL.revokeObjectURL(url);
  };
  const status = health?.status === "healthy" ? "Healthy" : health ? "Degraded" : "Unavailable";
  const demo = health?.sourceMode === "demo";
  return <SettingsGroup icon={HeartPulse} title="System health" description="Runtime metrics below come from the existing health endpoint; unsupported telemetry is labelled clearly.">
    <SettingRow title="Runtime status"><div className="flex flex-wrap items-center justify-end gap-2">{demo && <StatusPill tone="info">Demo data</StatusPill>}<StatusPill tone={health?.status === "healthy" ? "success" : health ? "warning" : "danger"}>{loading ? "Checking" : status}</StatusPill><button type="button" className="icon-button h-9 w-9" onClick={onRefresh} aria-label="Refresh system health"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button></div></SettingRow>
    <SettingRow title="Pipeline telemetry" stack>{error && <Notice tone="danger">The health endpoint could not be reached.</Notice>}<div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[
      { label: "Pipeline", value: health ? (health.pipelineRunning ? "Running" : "Stopped") : "—", icon: Activity },
      { label: "Analysis FPS", value: health ? health.analysisFps.toFixed(1) : "—", icon: CircleGauge },
      { label: "Active tracks", value: health ? String(health.activeTracks) : "—", icon: Radio },
      { label: "Source mode", value: health?.sourceMode || "—", icon: Video }
    ].map(({ label, value, icon: Icon }) => <div key={label} className="rounded-xl border border-border bg-surface-secondary/35 p-3"><Icon size={15} className="text-primary" /><p className="mt-3 text-[9px] font-bold uppercase tracking-wider text-muted">{label}</p><strong className="mt-1 block truncate text-sm">{value}</strong></div>)}</div></SettingRow>
    <SettingRow title="Compute and storage" description="The current API does not expose CPU, GPU, model version or disk capacity."><div className="grid gap-2 sm:grid-cols-3">{["CPU unavailable", "GPU unavailable", "Storage unavailable"].map((label) => <StatusPill key={label}>{label}</StatusPill>)}</div></SettingRow>
    <SettingRow title="Diagnostics and service controls" description="Download current health data. Restart remains disabled without a protected backend action."><div className="flex flex-wrap justify-end gap-2"><button type="button" className="secondary-button" onClick={downloadDiagnostics}><Download size={14} />Download diagnostics</button><button type="button" className="secondary-button" disabled title="No secure restart endpoint is available"><RefreshCw size={14} />Restart unavailable</button></div></SettingRow>
  </SettingsGroup>;
}

function AccountSection({ settings, onChange }: SectionProps) {
  const update = (patch: Partial<TrafficOpsSettings["account"]>) => onChange({ ...settings, account: { ...settings.account, ...patch } });
  return <SettingsGroup icon={UserRound} title="Account" description="Update local profile preferences for the signed-in operator.">
    <SettingRow title="Profile information" stack><div className="grid gap-3 sm:grid-cols-2"><TextField label="Display name" value={settings.account.name} onChange={(event) => update({ name: event.target.value })} /><TextField label="Email" type="email" value={settings.account.email} onChange={(event) => update({ email: event.target.value })} /><TextField label="Phone" type="tel" value={settings.account.phone} onChange={(event) => update({ phone: event.target.value })} /></div></SettingRow>
    <SettingRow title="Personal notifications" stack><ToggleGrid items={[{ label: "Assignment updates", checked: settings.account.notifyAssignments, onChange: (notifyAssignments) => update({ notifyAssignments }) }, { label: "Report completion", checked: settings.account.notifyReports, onChange: (notifyReports) => update({ notifyReports }) }]} /></SettingRow>
    <SettingRow title="Password" description="Password changes require a dedicated authenticated backend endpoint."><button type="button" className="secondary-button" disabled><KeyRound size={14} />Change password unavailable</button></SettingRow>
    <SettingRow title="Device sessions" description="The current authentication API supports signing out this session only."><button type="button" className="secondary-button" disabled><LockKeyhole size={14} />Log out all devices unavailable</button></SettingRow>
  </SettingsGroup>;
}

function DangerSection({ onReset }: { onReset: () => void }) {
  const [confirming, setConfirming] = useState(false);
  return <><SettingsGroup icon={ShieldAlert} title="Danger zone" description="Reset non-sensitive preferences stored by this browser. Backend data is never deleted here." tone="danger">
    <SettingRow title="Reset local settings" description="Restores defaults for every Settings category on this device."><button type="button" className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-danger/35 bg-danger/5 px-4 text-xs font-bold text-danger hover:bg-danger/10" onClick={() => setConfirming(true)}><Trash2 size={14} />Reset settings</button></SettingRow>
  </SettingsGroup><ConfirmDialog open={confirming} title="Reset all local settings?" description="This clears the browser-stored SadakDrishti settings and restores safe defaults. Existing traffic records, videos and backend configuration are not touched." confirmLabel="Reset settings" danger onCancel={() => setConfirming(false)} onConfirm={() => { setConfirming(false); onReset(); }} /></>;
}

export function SettingsSection({ section, settings, onChange, health, healthLoading, healthError, onRefreshHealth, onReset }: SectionProps & {
  section: SettingsSectionId;
  health?: SystemHealth;
  healthLoading: boolean;
  healthError: boolean;
  onRefreshHealth: () => void;
  onReset: () => void;
}) {
  switch (section) {
    case "general": return <GeneralSection settings={settings} onChange={onChange} />;
    case "cameras": return <CamerasSection settings={settings} onChange={onChange} />;
    case "detection": return <DetectionSection settings={settings} onChange={onChange} />;
    case "alerts": return <AlertsSection settings={settings} onChange={onChange} />;
    case "users": return <UsersSection settings={settings} onChange={onChange} />;
    case "recording": return <RecordingSection settings={settings} onChange={onChange} />;
    case "integrations": return <IntegrationsSection settings={settings} onChange={onChange} />;
    case "privacy": return <PrivacySection settings={settings} onChange={onChange} />;
    case "health": return <SystemHealthSection health={health} loading={healthLoading} error={healthError} onRefresh={onRefreshHealth} />;
    case "account": return <AccountSection settings={settings} onChange={onChange} />;
    case "danger": return <DangerSection onReset={onReset} />;
  }
}
