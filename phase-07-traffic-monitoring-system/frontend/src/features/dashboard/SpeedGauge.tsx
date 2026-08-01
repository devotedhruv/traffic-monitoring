import { cx, formatSpeed } from "../../lib/format";

export function SpeedGauge({ speed, limit = 50 }: { speed: number; limit?: number }) {
  const clamped = Math.min(140, Math.max(0, speed));
  const angle = -90 + (clamped / 140) * 180;
  const over = speed > limit;
  const x = 100 + 67 * Math.cos((angle * Math.PI) / 180);
  const y = 91 + 67 * Math.sin((angle * Math.PI) / 180);
  return (
    <div className="px-4 pb-4 pt-3" data-state={over ? "overspeed" : "normal"}>
      <svg viewBox="0 0 200 125" className="mx-auto block w-full max-w-xs" role="img" aria-label={`Current speed ${formatSpeed(speed)} kilometres per hour; speed limit ${limit}`}>
        <path d="M 25 92 A 75 75 0 0 1 175 92" fill="none" stroke="rgb(var(--color-line))" strokeWidth="13" strokeLinecap="round" />
        <path d="M 25 92 A 75 75 0 0 1 83.3 19" fill="none" stroke="rgb(var(--color-success))" strokeWidth="10" strokeLinecap="round" />
        <path d="M 88 17.8 A 75 75 0 0 1 134 25.2" fill="none" stroke="rgb(var(--color-amber))" strokeWidth="10" />
        <path d="M 138 27.5 A 75 75 0 0 1 175 92" fill="none" stroke="rgb(var(--color-danger))" strokeWidth="10" strokeLinecap="round" />
        <line className="transition-all duration-500" x1="100" y1="91" x2={x} y2={y} stroke={`rgb(var(--color-${over ? "danger" : "ink"}))`} strokeWidth="3.5" strokeLinecap="round" />
        <circle cx="100" cy="91" r="6" fill={`rgb(var(--color-${over ? "danger" : "ink"}))`} />
        <text x="100" y="115" textAnchor="middle" className={cx("fill-ink text-[17px] font-bold tabular-nums", over && "fill-danger")}>{formatSpeed(speed)}</text>
        <text x="100" y="124" textAnchor="middle" className="fill-muted text-[6px]">KM/H · LIMIT {limit}</text>
      </svg>
    </div>
  );
}
