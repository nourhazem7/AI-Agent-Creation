import { useState } from "react";
import { Button } from "../ui";

/** The SQL block itself — monospace text + Copy button, no toggle of its own. Split out so
 * callers that manage their own open/closed state (e.g. an accordion of several disclosures)
 * can reuse the exact same rendering as the self-toggling SqlDisclosure below. */
export function SqlBlock({ sql }: { sql: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="rounded-md border border-border bg-canvas p-3">
      <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-ink">{sql}</pre>
      <Button variant="ghost" size="sm" className="mt-2" onClick={handleCopy}>
        {copied ? "Copied" : "Copy"}
      </Button>
    </div>
  );
}

/** Expandable "technical detail" view of a SQL statement — collapsed by default so
 * non-technical users see the answer first, with SQL available on demand. Shared between
 * Chat (MessageBubble) and the Validation Workspace (TestCard) so both surfaces present
 * generated SQL identically. `label` customizes the trigger text ("View SQL" by default,
 * e.g. "agent SQL" for "View agent SQL") without changing behavior for existing callers. */
export function SqlDisclosure({ sql, label = "SQL" }: { sql: string; label?: string }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="text-xs font-medium text-ink-muted hover:text-ink"
      >
        {isOpen ? `Hide ${label}` : `View ${label}`}
      </button>
      {isOpen && (
        <div className="mt-2">
          <SqlBlock sql={sql} />
        </div>
      )}
    </div>
  );
}
