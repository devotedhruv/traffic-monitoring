import { useRef, useState, type MouseEvent } from "react";
import { CheckCircle2, Crosshair, RotateCcw, Undo2, X } from "lucide-react";
import type { NormalizedPoint } from "../../types";

const POINT_LABELS = ["Far left", "Far right", "Near right", "Near left"];

interface CalibrationEditorProps {
  previewUrl: string;
  filename: string;
  points: NormalizedPoint[];
  countingLinePosition: number;
  enabled: boolean;
  disabled?: boolean;
  onChange: (points: NormalizedPoint[]) => void;
  onRemove: () => void;
}

function percentage(value: number) {
  return `${(value * 100).toFixed(3)}%`;
}

export function CalibrationEditor({
  previewUrl,
  filename,
  points,
  countingLinePosition,
  enabled,
  disabled,
  onChange,
  onRemove
}: CalibrationEditorProps) {
  const video = useRef<HTMLVideoElement>(null);
  const [editing, setEditing] = useState(false);
  const [aspectRatio, setAspectRatio] = useState("16 / 9");

  const beginEditing = () => {
    video.current?.pause();
    setEditing(true);
  };

  const addPoint = (event: MouseEvent<HTMLDivElement>) => {
    if (!editing || points.length >= 4) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const next = [
      ...points,
      {
        x: Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width)),
        y: Math.min(1, Math.max(0, (event.clientY - bounds.top) / bounds.height))
      }
    ];
    onChange(next);
    if (next.length === 4) setEditing(false);
  };

  const line = points.length === 4 ? {
    left: {
      x: points[0].x * (1 - countingLinePosition) + points[3].x * countingLinePosition,
      y: points[0].y * (1 - countingLinePosition) + points[3].y * countingLinePosition
    },
    right: {
      x: points[1].x * (1 - countingLinePosition) + points[2].x * countingLinePosition,
      y: points[1].y * (1 - countingLinePosition) + points[2].y * countingLinePosition
    }
  } : null;

  return (
    <div className="space-y-3">
      <div
        className="relative overflow-hidden rounded-2xl border border-border bg-black"
        style={{ aspectRatio }}
      >
        <video
          ref={video}
          src={previewUrl}
          controls={!editing}
          onLoadedMetadata={(event) => {
            const element = event.currentTarget;
            if (element.videoWidth && element.videoHeight) {
              setAspectRatio(`${element.videoWidth} / ${element.videoHeight}`);
            }
          }}
          className="h-full w-full object-fill"
          aria-label={`Preview of ${filename}`}
        />

        {enabled && points.length > 0 && (
          <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            <polygon
              points={points.map((point) => `${point.x * 100},${point.y * 100}`).join(" ")}
              fill="rgb(var(--color-primary) / .13)"
              stroke="rgb(var(--color-primary))"
              strokeWidth="0.35"
              strokeDasharray={points.length < 4 ? "1.2 1.2" : undefined}
              vectorEffect="non-scaling-stroke"
            />
            {line && <line x1={line.left.x * 100} y1={line.left.y * 100} x2={line.right.x * 100} y2={line.right.y * 100} stroke="#facc15" strokeWidth="0.55" vectorEffect="non-scaling-stroke" />}
          </svg>
        )}

        {enabled && points.map((point, index) => (
          <span
            key={`${point.x}-${point.y}-${index}`}
            className="pointer-events-none absolute grid h-7 w-7 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border-2 border-white bg-primary text-[10px] font-black text-white shadow-lg"
            style={{ left: percentage(point.x), top: percentage(point.y) }}
          >
            {index + 1}
          </span>
        ))}

        {editing && enabled && (
          <div
            role="button"
            tabIndex={0}
            onClick={addPoint}
            onKeyDown={(event) => { if (event.key === "Escape") setEditing(false); }}
            className="absolute inset-0 cursor-crosshair bg-black/10 outline-none ring-inset focus-visible:ring-2 focus-visible:ring-primary"
            aria-label={`Mark ${POINT_LABELS[points.length] ?? "road"} calibration point. Press Escape to stop.`}
          >
            <span className="absolute left-1/2 top-3 -translate-x-1/2 rounded-full bg-black/80 px-3 py-1.5 text-[10px] font-bold text-white">
              Click {points.length + 1}: {POINT_LABELS[points.length]}
            </span>
          </div>
        )}

        {!disabled && (
          <button type="button" onClick={onRemove} className="absolute right-3 top-3 grid h-10 w-10 place-items-center rounded-full bg-black/75 text-white hover:bg-black" aria-label="Remove selected video">
            <X size={16} />
          </button>
        )}
      </div>

      {enabled && (
        <div className="rounded-xl border border-primary/20 bg-primary-soft p-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-bold text-secondary">
                {points.length === 4 ? <span className="inline-flex items-center gap-1.5 text-success"><CheckCircle2 size={14} />Road plane calibrated</span> : `${points.length} of 4 road points marked`}
              </p>
              <p className="mt-1 text-[10px] text-muted">Order: far-left, far-right, near-right, near-left.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {points.length > 0 && <button type="button" disabled={disabled} onClick={() => onChange(points.slice(0, -1))} className="secondary-button min-h-10"><Undo2 size={14} />Undo</button>}
              {points.length > 0 && <button type="button" disabled={disabled} onClick={() => onChange([])} className="secondary-button min-h-10"><RotateCcw size={14} />Reset</button>}
              <button type="button" disabled={disabled || points.length === 4} onClick={beginEditing} className="secondary-button min-h-10 border-primary/30 text-primary"><Crosshair size={14} />{points.length ? "Continue marking" : "Mark road plane"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
