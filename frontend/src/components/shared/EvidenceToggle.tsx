/** Compact `▸/▾ label` trigger for a collapsed-by-default secondary-evidence section (SQL,
 * result data, diagnostic reference, ...). Shared between the Validation Workspace's
 * TestCard and Chat's MessageBubble so both surfaces use the same disclosure language —
 * this button only renders the trigger; the caller owns which section's content is shown
 * below it (see either component for the accordion pattern). */
export function EvidenceToggle({
  isOpen,
  label,
  onClick,
}: {
  isOpen: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`text-xs font-medium hover:text-ink ${isOpen ? "text-ink" : "text-ink-muted"}`}
    >
      {isOpen ? "▾" : "▸"} {label}
    </button>
  );
}
