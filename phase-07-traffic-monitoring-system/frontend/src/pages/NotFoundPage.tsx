import { ArrowLeft, MapPinOff } from "lucide-react";
import { Link } from "../components/ui/Link";

export function NotFoundPage({ inApp = false }: { inApp?: boolean }) {
  return <div className="grid min-h-[70vh] place-items-center px-5 text-center"><div><MapPinOff className="mx-auto mb-4 text-primary" size={42} /><p className="text-xs font-bold tracking-[0.2em] text-muted">ERROR 404</p><h1 className="mt-2 text-3xl font-bold">Route not monitored</h1><p className="mt-2 text-sm text-muted">This control-room view does not exist.</p><Link to={inApp ? "/app" : "/"} className="primary-button mt-6"><ArrowLeft size={16} />{inApp ? "Return to dashboard" : "Return home"}</Link></div></div>;
}
