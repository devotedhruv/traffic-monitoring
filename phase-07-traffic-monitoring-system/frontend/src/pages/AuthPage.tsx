import { useState, type FormEvent } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, Eye, EyeOff, LockKeyhole, Mail, ScanLine, ShieldCheck, UserRound } from "lucide-react";
import { useAuth } from "../app/AuthContext";
import { navigate } from "../app/router";
import { Link } from "../components/ui/Link";
import { LanguageToggle } from "../components/ui/LanguageToggle";
import { BrandLogo } from "../components/ui/BrandLogo";
import { PRODUCT_NAME } from "../lib/brand";
import { LoadingSkeleton } from "../components/ui/States";

function safeDestination() {
  const destination = new URLSearchParams(window.location.search).get("next");
  return destination?.startsWith("/app") && !destination.startsWith("//") ? destination : "/app";
}

const commonEmailDomainTypos: Record<string, string> = {
  "gmaiil.com": "gmail.com",
  "gmial.com": "gmail.com",
  "gmal.com": "gmail.com",
  "gmail.co": "gmail.com",
  "gmail.con": "gmail.com"
};

function emailSuggestion(email: string) {
  const separator = email.lastIndexOf("@");
  if (separator <= 0) return null;
  const localPart = email.slice(0, separator);
  const correctedDomain = commonEmailDomainTypos[email.slice(separator + 1).toLowerCase()];
  return correctedDomain ? `${localPart}@${correctedDomain}` : null;
}

export function AuthPage({ mode }: { mode: "signin" | "signup" }) {
  const isSignup = mode === "signup";
  const { status, user, signIn, signUp } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    const normalizedEmail = email.trim();
    if (isSignup && name.trim().length < 2) return setError("Please enter your full name.");
    if (!normalizedEmail || !normalizedEmail.includes("@")) return setError("Please enter a valid email address.");
    const suggestedEmail = isSignup ? emailSuggestion(normalizedEmail) : null;
    if (suggestedEmail) return setError(`Check your email address. Did you mean ${suggestedEmail}?`);
    if (password.length < 8) return setError("Password must be at least 8 characters.");
    if (isSignup && password !== confirmPassword) return setError("Passwords do not match.");
    setSubmitting(true);
    try {
      if (isSignup) await signUp(name.trim(), normalizedEmail, password);
      else await signIn(normalizedEmail, password);
      navigate(safeDestination());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We could not complete your request. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (status === "loading") return <div className="mx-auto mt-24 max-w-md px-5"><LoadingSkeleton className="h-[520px]" /></div>;

  return (
    <div className="min-h-screen bg-page">
      <header className="absolute inset-x-0 top-0 z-20">
        <div className="mx-auto flex h-[76px] max-w-[1240px] items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link to="/" className="flex items-center gap-2.5" aria-label={`${PRODUCT_NAME} home`}><BrandLogo variant="mark" className="h-10 w-12 rounded-xl bg-white p-0.5 shadow-card" /><strong className="text-sm text-primary">Sadak<span className="text-danger">Drishti</span></strong></Link>
          <LanguageToggle />
        </div>
      </header>
      <main className="grid min-h-screen lg:grid-cols-[1.05fr_.95fr]">
        <section className="relative hidden overflow-hidden bg-[#245DB3] px-12 pb-14 pt-28 text-white lg:flex lg:flex-col">
          <div className="landing-grid-dark absolute inset-0 opacity-80" />
          <div className="absolute -left-20 top-20 h-80 w-80 rounded-full bg-[#DC143C]/15 blur-3xl" />
          <div className="absolute -bottom-20 right-0 h-96 w-96 rounded-full bg-[#60A5FA]/12 blur-3xl" />
          <div className="relative mx-auto flex w-full max-w-[570px] flex-1 flex-col justify-center">
            <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.17em] text-[#BFDBFE]"><ScanLine size={15} />Intelligence in motion</p>
            <h1 className="mt-6 text-[46px] font-extrabold leading-[1.08] tracking-[-0.05em]">Your traffic operations,<br/><span className="text-[#FF8395]">clear and connected.</span></h1>
            <p className="mt-5 max-w-lg text-sm leading-7 text-white/55">Monitor the live road, find important events faster, and turn video into useful operational evidence from one secure workspace.</p>
            <div className="mt-10 grid max-w-lg gap-3 sm:grid-cols-3">
              {[
                [ScanLine, "Detection", "AI-assisted"],
                [LockKeyhole, "Access", "Session secured"],
                [ShieldCheck, "Data", "Self-host ready"]
              ].map(([Icon, title, note]) => {
                const ItemIcon = Icon as typeof ScanLine;
                return <div key={String(title)} className="rounded-2xl border border-white/10 bg-white/[0.045] p-4"><ItemIcon size={18} className="text-[#BFDBFE]" /><strong className="mt-3 block text-[10px]">{String(title)}</strong><span className="mt-1 block text-[8px] text-white/40">{String(note)}</span></div>;
              })}
            </div>
          </div>
          <p className="relative mx-auto w-full max-w-[570px] text-[9px] text-white/30">Road intelligence, made visible.</p>
        </section>

        <section className="relative flex items-center justify-center px-4 pb-12 pt-24 sm:px-8">
          <div className="w-full max-w-[430px]">
            <Link to="/" className="mb-8 inline-flex items-center gap-2 text-[11px] font-semibold text-muted hover:text-primary"><ArrowLeft size={14} />Back to home</Link>
            {status === "authenticated" && user ? (
              <div className="rounded-3xl border border-border bg-surface p-7 text-center shadow-panel sm:p-9">
                <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-primary-soft text-primary"><CheckCircle2 size={25} /></span>
                <h1 className="mt-5 text-2xl font-extrabold tracking-tight">You’re already signed in</h1>
                <p className="mt-2 text-sm text-muted">Continue to SadakDrishti as {user.email}.</p>
                <Link to="/app" className="primary-button mt-7 w-full">Open operations console<ArrowRight size={16} /></Link>
              </div>
            ) : (
              <>
                <div><p className="eyebrow">{isSignup ? "Create your workspace access" : "Welcome back"}</p><h1 className="mt-3 text-[32px] font-extrabold tracking-[-0.04em]">{isSignup ? "Start with SadakDrishti." : "Sign in to your console."}</h1><p className="mt-2 text-sm leading-6 text-muted">{isSignup ? "Create an account to access live monitoring and traffic analysis." : "Use your account details to continue monitoring operations."}</p></div>
                <form className="mt-8 space-y-4" onSubmit={submit} noValidate>
                  {isSignup && <label className="block"><span className="mb-2 block text-[11px] font-bold text-secondary">Full name</span><span className="relative block"><UserRound className="absolute left-3.5 top-3.5 text-muted" size={16} /><input className="field h-12 pl-10" value={name} onChange={(event) => setName(event.target.value)} placeholder="Traffic operator" autoComplete="name" required /></span></label>}
                  <label className="block"><span className="mb-2 block text-[11px] font-bold text-secondary">Email address</span><span className="relative block"><Mail className="absolute left-3.5 top-3.5 text-muted" size={16} /><input className="field h-12 pl-10" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@organization.com" autoComplete="email" required /></span></label>
                  <label className="block"><span className="mb-2 block text-[11px] font-bold text-secondary">Password</span><span className="relative block"><LockKeyhole className="absolute left-3.5 top-3.5 text-muted" size={16} /><input className="field h-12 px-10" type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} placeholder={isSignup ? "At least 8 characters" : "Enter your password"} autoComplete={isSignup ? "new-password" : "current-password"} required /><button type="button" className="absolute right-1.5 top-1.5 grid h-9 w-9 place-items-center rounded-lg text-muted hover:bg-elevated hover:text-ink" onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button></span></label>
                  {isSignup && <label className="block"><span className="mb-2 block text-[11px] font-bold text-secondary">Confirm password</span><span className="relative block"><LockKeyhole className="absolute left-3.5 top-3.5 text-muted" size={16} /><input className="field h-12 pl-10" type={showPassword ? "text" : "password"} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="Repeat your password" autoComplete="new-password" required /></span></label>}
                  {error && <div role="alert" className="rounded-xl border border-danger/20 bg-danger-dark px-3.5 py-3 text-[11px] font-semibold text-danger">{error}</div>}
                  <button className="primary-button mt-2 w-full" type="submit" disabled={submitting}>{submitting ? "Please wait…" : isSignup ? "Create account" : "Sign in"}<ArrowRight size={16} /></button>
                </form>
                <p className="mt-6 text-center text-xs text-muted">{isSignup ? "Already have an account?" : "New to SadakDrishti?"} <Link to={isSignup ? "/sign-in" : "/sign-up"} className="font-bold text-primary hover:text-primary-hover">{isSignup ? "Sign in" : "Create an account"}</Link></p>
                <div className="mt-7 flex items-center justify-center gap-2 border-t border-border pt-5 text-[9px] text-muted"><ShieldCheck size={13} className="text-primary" />Passwords are securely hashed; sessions can be revoked on sign out.</div>
              </>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
