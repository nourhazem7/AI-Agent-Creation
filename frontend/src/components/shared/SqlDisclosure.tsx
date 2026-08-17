import { useState } from "react";
import { Button } from "../ui";

/** Expandable "technical detail" view of a SQL statement — collapsed by default so
 * non-technical users see the answer first, with SQL available on demand. Shared between
 * Chat (MessageBubble) and the Validation Workspace (TestCard) so both surfaces present
 * generated SQL identically. */
export function SqlDisclosure({ sql }: { sql: string }) {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="text-xs font-medium text-ink-muted hover:text-ink"
      >
        {isOpen ? "Hide SQL" : "View SQL"}
      </button>
      {isOpen && (
        <div className="mt-2 rounded-md border border-border bg-canvas p-3">
          <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-ink">{sql}</pre>
          <Button variant="ghost" size="sm" className="mt-2" onClick={handleCopy}>
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
      )}
    </div>
  );
}
