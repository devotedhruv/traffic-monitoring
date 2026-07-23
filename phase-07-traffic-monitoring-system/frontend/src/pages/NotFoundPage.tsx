import { ArrowLeft, MapPinOff } from "lucide-react";
import { Link } from "react-router-dom";

export function NotFoundPage() {
  return <div className="grid min-h-[70vh] place-items-center text-center"><div><MapPinOff className="mx-auto mb-4 text-cyan" size={42} /><p className="text-xs font-bold tracking-[0.2em] text-muted">ERROR 404</p><h1 className="mt-2 text-3xl font-bold">Route not monitored</h1><p className="mt-2 text-sm text-muted">This control-room view does not exist.</p><Link to="/" className="mt-6 inline-flex items-center gap-2 rounded bg-cyan px-4 py-2 text-sm font-bold text-page"><ArrowLeft size={16} />Return to dashboard</Link></div></div>;
}
