type Status = "idle" | "pending" | "success" | "error";

interface StatusIndicatorProps {
  status: Status;
  label: string;
  className?: string;
}

const dotClasses: Record<Status, string> = {
  idle: "bg-ink-muted",
  pending: "bg-warning animate-pulse",
  success: "bg-success",
  error: "bg-danger",
};

export function StatusIndicator({ status, label, className = "" }: StatusIndicatorProps) {
  return (
    <span className={`inline-flex items-center gap-2 text-sm text-ink ${className}`} aria-live="polite">
      <span className={`h-2 w-2 rounded-full ${dotClasses[status]}`} aria-hidden="true" />
      {label}
    </span>
  );
}
