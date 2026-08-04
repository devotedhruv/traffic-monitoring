import {
  Activity, ArrowRight, BarChart3, BellRing, Camera, CheckCircle2, CircleGauge,
  Database, Gauge, MapPin, Play, Radio, ScanLine, ShieldCheck, Sparkles,
  Upload, Zap
} from "lucide-react";
import { useAuth } from "../app/AuthContext";
import { Link } from "../components/ui/Link";
import { ThemeToggle } from "../components/ui/ThemeToggle";

function Brand() {
  return (
    <Link to="/" className="flex items-center gap-2.5" aria-label="TrafficOps AI home">
      <span className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-primary to-primary-hover text-white shadow-card"><Activity size={21} /></span>
      <span className="text-[15px] font-extrabold tracking-[-0.03em]">TrafficOps <span className="text-primary">AI</span></span>
    </Link>
  );
}

function PublicHeader() {
  const { status } = useAuth();
  const signedIn = status === "authenticated";
  return (
    <header className="sticky top-0 z-50 border-b border-border/80 bg-page/80 backdrop-blur-xl">
      <div className="mx-auto flex h-[72px] max-w-[1240px] items-center gap-6 px-4 sm:px-6 lg:px-8">
        <Brand />
        <nav className="ml-auto hidden items-center gap-7 md:flex" aria-label="Landing page">
          <a href="#platform" className="text-xs font-semibold text-secondary hover:text-primary">Platform</a>
          <a href="#capabilities" className="text-xs font-semibold text-secondary hover:text-primary">Capabilities</a>
          <a href="#workflow" className="text-xs font-semibold text-secondary hover:text-primary">How it works</a>
        </nav>
        <div className="ml-auto flex items-center gap-2 md:ml-0">
          <ThemeToggle />
          {!signedIn && <Link to="/sign-in" className="hidden h-10 items-center px-3 text-xs font-bold text-secondary hover:text-primary sm:inline-flex">Sign in</Link>}
          <Link to={signedIn ? "/app" : "/sign-up"} className="inline-flex h-10 items-center gap-2 rounded-xl bg-ink px-4 text-xs font-bold text-page hover:opacity-85">
            {signedIn ? "Open console" : "Get started"}<ArrowRight size={14} />
          </Link>
        </div>
      </div>
    </header>
  );
}

function TrafficPreview() {
  return (
    <div className="hero-preview relative mx-auto w-full max-w-[570px]" aria-label="Preview of the live traffic operations dashboard">
      <div className="absolute -left-12 top-20 h-40 w-40 rounded-full bg-primary/15 blur-3xl" />
      <div className="absolute -right-8 bottom-10 h-44 w-44 rounded-full bg-cyan/10 blur-3xl" />
      <div className="relative overflow-hidden rounded-[26px] border border-white/10 bg-[#08120f] p-3 shadow-[0_35px_80px_-25px_rgb(0_0_0/0.55)] sm:p-4">
        <div className="flex items-center gap-2 border-b border-white/10 px-1 pb-3 text-white">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-emerald-500"><Activity size={14} /></span>
          <div><strong className="block text-[10px]">TrafficOps AI</strong><span className="block text-[7px] text-white/45">Live operations console</span></div>
          <div className="ml-auto flex items-center gap-1.5 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-1 text-[7px] font-bold text-emerald-300"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> LIVE</div>
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2">
          {[
            ["Vehicles", "1,284", "+12%"], ["Avg. speed", "38.6", "km/h"], ["Violations", "24", "1.9%"]
          ].map(([label, value, note]) => (
            <div key={label} className="rounded-xl border border-white/10 bg-white/[0.045] p-2.5">
              <span className="block text-[7px] font-semibold uppercase tracking-wider text-white/40">{label}</span>
              <strong className="mt-1.5 block text-sm tracking-tight text-white sm:text-base">{value}</strong>
              <span className="text-[7px] text-emerald-300">{note}</span>
            </div>
          ))}
        </div>
        <div className="mt-2 grid gap-2 sm:grid-cols-[1.55fr_1fr]">
          <div className="relative min-h-[228px] overflow-hidden rounded-2xl border border-white/10 bg-[#101c18]">
            <div className="absolute inset-x-3 top-3 z-10 flex items-center justify-between text-white">
              <span className="flex items-center gap-1.5 text-[8px] font-bold"><Camera size={10} className="text-emerald-400" />North Junction</span>
              <span className="rounded-md bg-black/35 px-1.5 py-1 text-[7px] text-white/60">CAM 01</span>
            </div>
            <svg viewBox="0 0 420 245" className="absolute inset-0 h-full w-full" role="img" aria-label="AI tracking vehicles across an intersection">
              <defs>
                <linearGradient id="road" x1="0" x2="1"><stop stopColor="#172a23"/><stop offset="1" stopColor="#0e1d18"/></linearGradient>
                <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#6ee7b7" strokeOpacity=".045"/></pattern>
              </defs>
              <rect width="420" height="245" fill="url(#road)"/><rect width="420" height="245" fill="url(#grid)"/>
              <path d="M-20 195C90 155 112 101 212 93C310 85 350 44 445 15" fill="none" stroke="#283c34" strokeWidth="94"/>
              <path d="M-20 195C90 155 112 101 212 93C310 85 350 44 445 15" fill="none" stroke="#f8fafc" strokeOpacity=".22" strokeWidth="2" strokeDasharray="17 15"/>
              <path d="M48 245C92 174 142 151 216 133C298 113 337 74 381 -8" fill="none" stroke="#f8fafc" strokeOpacity=".12" strokeWidth="1"/>
              <g className="vehicle-box"><rect x="119" y="126" width="57" height="35" rx="4" fill="#22c55e" fillOpacity=".08" stroke="#4ade80" strokeWidth="1.5"/><rect x="137" y="135" width="20" height="12" rx="3" fill="#d1fae5"/><text x="119" y="120" fill="#86efac" fontSize="8" fontWeight="700">CAR · 42 KM/H</text></g>
              <g><rect x="257" y="68" width="62" height="39" rx="4" fill="#f59e0b" fillOpacity=".08" stroke="#fbbf24" strokeWidth="1.5"/><rect x="278" y="78" width="21" height="14" rx="3" fill="#fef3c7"/><text x="257" y="62" fill="#fde68a" fontSize="8" fontWeight="700">CAR · 61 KM/H</text></g>
              <g><rect x="56" y="169" width="50" height="30" rx="4" fill="#22c55e" fillOpacity=".08" stroke="#4ade80"/><text x="56" y="164" fill="#86efac" fontSize="7">BIKE · 31 KM/H</text></g>
            </svg>
            <div className="absolute bottom-3 left-3 flex gap-2 text-[7px]"><span className="rounded-md bg-black/45 px-2 py-1.5 text-emerald-300">3 TRACKED</span><span className="rounded-md bg-black/45 px-2 py-1.5 text-white/55">15.2 FPS</span></div>
          </div>
          <div className="space-y-2">
            <div className="rounded-2xl border border-white/10 bg-white/[0.045] p-3">
              <div className="flex items-center justify-between"><span className="text-[8px] font-semibold text-white/50">Traffic flow</span><BarChart3 size={11} className="text-emerald-400" /></div>
              <div className="mt-4 flex h-[62px] items-end gap-1.5">
                {[34, 54, 42, 68, 58, 84, 70, 92, 77, 64].map((height, index) => <span key={index} className="flex-1 rounded-t-sm bg-emerald-400/70" style={{ height: `${height}%`, opacity: .45 + index * .045 }} />)}
              </div>
              <div className="mt-2 flex justify-between text-[6px] text-white/30"><span>08:00</span><span>NOW</span></div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.045] p-3">
              <span className="text-[8px] font-semibold text-white/50">Recent event</span>
              <div className="mt-3 flex gap-2"><span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-amber-400/10 text-amber-300"><Gauge size={13} /></span><div><strong className="block text-[8px] text-white">Speed threshold</strong><span className="text-[7px] text-white/40">BA 12 PA 1234</span></div><strong className="ml-auto text-[8px] text-amber-300">61</strong></div>
            </div>
          </div>
        </div>
      </div>
      <div className="preview-float absolute -bottom-5 -left-3 hidden items-center gap-3 rounded-2xl border border-border bg-surface px-4 py-3 shadow-panel sm:flex">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary-soft text-primary"><ScanLine size={18} /></span>
        <span><strong className="block text-[10px]">AI detection active</strong><small className="text-[8px] text-muted">Vehicles tracked in real time</small></span>
        <CheckCircle2 size={16} className="ml-2 text-success" />
      </div>
    </div>
  );
}

const capabilities = [
  { icon: ScanLine, title: "Vehicle intelligence", text: "Detect, classify, and track cars, buses, trucks, and motorcycles across every frame." },
  { icon: CircleGauge, title: "Speed monitoring", text: "Turn calibrated camera footage into clear speed insights and threshold-based violations." },
  { icon: BellRing, title: "Actionable alerts", text: "Surface overspeed events with timestamps, vehicle details, and searchable history." },
  { icon: BarChart3, title: "Operational analytics", text: "Understand traffic volume, fleet mix, average speed, and peak periods at a glance." },
  { icon: Upload, title: "Video analysis", text: "Upload road footage or queue a supported public video link for on-demand processing." },
  { icon: Database, title: "Local data control", text: "Keep detections and operational records in your own deployment and database." }
];

export function LandingPage() {
  const { status } = useAuth();
  const consolePath = status === "authenticated" ? "/app" : "/sign-up";
  return (
    <div className="min-h-screen overflow-hidden bg-page text-ink">
      <PublicHeader />
      <main>
        <section className="relative">
          <div className="landing-grid absolute inset-0 opacity-70" />
          <div className="relative mx-auto grid max-w-[1240px] items-center gap-14 px-4 pb-24 pt-16 sm:px-6 sm:pt-20 lg:grid-cols-[.9fr_1.1fr] lg:px-8 lg:pb-28 lg:pt-24">
            <div className="max-w-[600px]">
              <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary-soft px-3 py-1.5 text-[10px] font-bold text-primary"><Sparkles size={13} />AI-powered road intelligence</div>
              <h1 className="mt-6 text-[42px] font-extrabold leading-[1.04] tracking-[-0.055em] sm:text-[58px] lg:text-[64px]">See every road.<br/><span className="text-primary">Understand every move.</span></h1>
              <p className="mt-6 max-w-[540px] text-[15px] leading-7 text-secondary sm:text-base">TrafficOps AI turns ordinary camera feeds into a live operations layer—helping teams detect vehicles, monitor speed, investigate events, and make roads safer.</p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link to={consolePath} className="primary-button h-13 px-6">{status === "authenticated" ? "Open operations console" : "Start monitoring"}<ArrowRight size={17} /></Link>
                <a href="#workflow" className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-border bg-surface px-5 text-sm font-bold text-secondary shadow-sm hover:border-border-strong hover:text-ink"><span className="grid h-6 w-6 place-items-center rounded-full bg-primary-soft text-primary"><Play size={11} fill="currentColor" /></span>See how it works</a>
              </div>
              <div className="mt-8 flex flex-wrap gap-x-5 gap-y-2 text-[10px] font-semibold text-muted">
                <span className="flex items-center gap-1.5"><CheckCircle2 size={13} className="text-primary" />FastAPI + React</span>
                <span className="flex items-center gap-1.5"><CheckCircle2 size={13} className="text-primary" />Real-time WebSocket feed</span>
                <span className="flex items-center gap-1.5"><CheckCircle2 size={13} className="text-primary" />Self-host ready</span>
              </div>
            </div>
            <TrafficPreview />
          </div>
        </section>

        <section className="border-y border-border bg-surface/70" id="platform">
          <div className="mx-auto grid max-w-[1240px] grid-cols-2 divide-x divide-border px-4 sm:px-6 md:grid-cols-4 lg:px-8">
            {[
              [Radio, "Live monitoring", "Continuous operational view"],
              [Zap, "Instant events", "Real-time detection updates"],
              [ShieldCheck, "Secure access", "Revocable server sessions"],
              [MapPin, "Camera-aware", "Built for monitored locations"]
            ].map(([Icon, title, text]) => {
              const FeatureIcon = Icon as typeof Radio;
              return <div key={String(title)} className="px-4 py-7 text-center sm:px-6"><FeatureIcon className="mx-auto text-primary" size={19} /><strong className="mt-2 block text-[11px]">{String(title)}</strong><span className="mt-1 block text-[8px] text-muted sm:text-[9px]">{String(text)}</span></div>;
            })}
          </div>
        </section>

        <section id="capabilities" className="mx-auto max-w-[1240px] px-4 py-24 sm:px-6 lg:px-8 lg:py-28">
          <div className="max-w-2xl"><p className="eyebrow">One intelligent platform</p><h2 className="mt-3 text-3xl font-extrabold tracking-[-0.04em] sm:text-4xl">From camera feed to confident decision.</h2><p className="mt-4 text-sm leading-6 text-secondary">Every capability is designed around the daily questions traffic teams need answered—what happened, where, when, and what needs attention now.</p></div>
          <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {capabilities.map(({ icon: Icon, title, text }, index) => <article key={title} className="group rounded-2xl border border-border bg-surface p-6 shadow-[0_8px_30px_rgb(16_24_40/0.025)] hover:-translate-y-1 hover:border-primary/25 hover:shadow-panel"><div className="flex items-center justify-between"><span className="grid h-11 w-11 place-items-center rounded-xl bg-primary-soft text-primary"><Icon size={21} /></span><span className="text-[9px] font-bold text-muted/50">0{index + 1}</span></div><h3 className="mt-6 text-[15px] font-bold">{title}</h3><p className="mt-2 text-xs leading-5 text-muted">{text}</p></article>)}
          </div>
        </section>

        <section id="workflow" className="border-y border-border bg-surface-secondary/55">
          <div className="mx-auto max-w-[1240px] px-4 py-24 sm:px-6 lg:px-8 lg:py-28">
            <div className="mx-auto max-w-2xl text-center"><p className="eyebrow">Simple by design</p><h2 className="mt-3 text-3xl font-extrabold tracking-[-0.04em] sm:text-4xl">Go from footage to insight in three steps.</h2></div>
            <div className="relative mt-14 grid gap-5 md:grid-cols-3">
              <div className="absolute left-[16%] right-[16%] top-8 hidden border-t border-dashed border-primary/25 md:block" />
              {[
                [Camera, "Connect your source", "Use the configured live camera or bring a road video into the analysis workspace."],
                [ScanLine, "Let the pipeline observe", "Detection, tracking, speed estimation, and event classification run through one workflow."],
                [BarChart3, "Act on the signal", "Review live status, explore vehicle history, and compare operational trends over time."]
              ].map(([Icon, title, text], index) => {
                const StepIcon = Icon as typeof Camera;
                return <article key={String(title)} className="relative rounded-2xl border border-border bg-surface p-6 text-center shadow-card"><span className="relative mx-auto grid h-16 w-16 place-items-center rounded-2xl border border-primary/20 bg-primary-soft text-primary"><StepIcon size={25} /><small className="absolute -right-2 -top-2 grid h-6 w-6 place-items-center rounded-full bg-primary text-[9px] font-bold text-white">{index + 1}</small></span><h3 className="mt-6 text-[15px] font-bold">{String(title)}</h3><p className="mx-auto mt-2 max-w-[280px] text-xs leading-5 text-muted">{String(text)}</p></article>;
              })}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-[1240px] px-4 py-24 sm:px-6 lg:px-8">
          <div className="relative overflow-hidden rounded-[28px] bg-[#091510] px-6 py-14 text-center text-white sm:px-12 sm:py-16">
            <div className="landing-grid-dark absolute inset-0" />
            <div className="absolute left-1/2 top-0 h-60 w-60 -translate-x-1/2 rounded-full bg-emerald-500/20 blur-3xl" />
            <div className="relative mx-auto max-w-2xl"><span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-emerald-500 text-white"><Activity size={23} /></span><h2 className="mt-6 text-3xl font-extrabold tracking-[-0.04em] sm:text-4xl">Make every camera count.</h2><p className="mx-auto mt-4 max-w-xl text-sm leading-6 text-white/55">Bring detection, speed insights, vehicle history, and video analysis into one focused traffic operations console.</p><Link to={consolePath} className="mt-8 inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-white px-6 text-sm font-bold text-[#091510] hover:bg-emerald-50">{status === "authenticated" ? "Open TrafficOps" : "Create your account"}<ArrowRight size={16} /></Link></div>
          </div>
        </section>
      </main>
      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-[1240px] flex-col items-center justify-between gap-4 px-4 py-8 text-center sm:flex-row sm:px-6 sm:text-left lg:px-8"><Brand /><p className="text-[10px] text-muted">AI-assisted traffic intelligence for safer, more observable roads.</p><div className="flex gap-5 text-[10px] font-semibold text-muted"><a href="#capabilities" className="hover:text-primary">Capabilities</a><a href="#workflow" className="hover:text-primary">Workflow</a></div></div>
      </footer>
    </div>
  );
}
