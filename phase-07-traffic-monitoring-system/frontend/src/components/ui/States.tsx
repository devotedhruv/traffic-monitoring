import { AlertCircle, Inbox } from "lucide-react";

export function LoadingSkeleton({ className = "h-20" }: { className?: string }) {
  return <div aria-label="Loading" className={`${className} animate-pulse rounded-md bg-elevated`} />;
}

export function EmptyState({ title = "No detections found", message = "New vehicle detections will appear here." }: { title?: string; message?: string }) {
  return (
    <div className="grid min-h-48 place-items-center p-8 text-center">
      <div><Inbox className="mx-auto mb-3 text-muted" aria-hidden="true" /><p className="font-semibold">{title}</p><p className="mt-1 text-sm text-muted">{message}</p></div>
    </div>
  );
}

export function ErrorState({ message = "Unable to load this data." }: { message?: string }) {
  return <div role="alert" className="flex min-h-32 items-center justify-center gap-2 p-6 text-sm text-danger"><AlertCircle size={18} />{message}</div>;
}
