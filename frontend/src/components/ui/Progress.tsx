interface ProgressProps {
  value: number; // 0-100
  label?: string;
  className?: string;
}

export function Progress({ value, label, className = "" }: ProgressProps) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div className={className}>
      {label && (
        <div className="mb-1.5 flex items-center justify-between text-sm text-ink-muted">
          <span>{label}</span>
          <span>{Math.round(clamped)}%</span>
        </div>
      )}
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-border"
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full rounded-full bg-ink transition-[width] duration-300 ease-out"
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}
