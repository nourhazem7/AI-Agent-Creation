import { useState } from "react";
import { Badge } from "../ui";
import { EvidenceToggle } from "../shared/EvidenceToggle";
import { SqlBlock } from "../shared/SqlDisclosure";
import type { ChatMessage } from "../../api/chat";

function parseResultRows(json: string | null): Record<string, unknown>[] {
  if (!json) return [];
  try {
    const parsed = JSON.parse(json);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function ResultTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (rows.length === 0) return null;
  const columns = Object.keys(rows[0]);
  const shown = rows.slice(0, 50);

  return (
    <div className="mt-2 overflow-x-auto rounded-md border border-border">
      <table className="w-full text-left text-sm">
        <thead className="bg-canvas text-ink-muted">
          <tr>
            {columns.map((col) => (
              <th key={col} className="px-3 py-2 font-medium">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((row, i) => (
            <tr key={i} className="border-t border-border">
              {columns.map((col) => (
                <td key={col} className="px-3 py-2 text-ink">
                  {String(row[col] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > shown.length && (
        <p className="border-t border-border px-3 py-2 text-xs text-ink-muted">
          Showing {shown.length} of {rows.length} rows
        </p>
      )}
    </div>
  );
}

// Employee-facing hierarchy: Answer -> View data -> View SQL. Both collapsed by default, one
// open at a time. raw_answer is intentionally never wired in here — it's preserved on the
// message for debugging/API inspection, not exposed as a normal Chat control.
type EvidenceSection = "data" | "sql" | "error" | null;

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const [openSection, setOpenSection] = useState<EvidenceSection>(null);
  const [copied, setCopied] = useState(false);
  const rows = message.response_type === "table" ? parseResultRows(message.result_data) : [];

  function toggle(section: EvidenceSection) {
    setOpenSection((prev) => (prev === section ? null : section));
  }

  async function handleCopyAnswer() {
    // Only the normalized, employee-facing text — never SQL, raw response, or table data.
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-2xl rounded-lg bg-ink px-4 py-2.5 text-sm text-white">{message.content}</div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-2xl rounded-lg border border-border bg-surface px-4 py-3">
        {message.error_message && <Badge tone="danger">Error</Badge>}
        <p className={`whitespace-pre-wrap text-sm text-ink ${message.error_message ? "mt-1.5" : ""}`}>
          {message.content}
        </p>

        <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border pt-2">
          {!message.error_message && (
            <button
              type="button"
              onClick={handleCopyAnswer}
              className="text-xs font-medium text-ink-muted hover:text-ink"
            >
              {copied ? "Copied" : "Copy answer"}
            </button>
          )}
          {rows.length > 0 && (
            <EvidenceToggle isOpen={openSection === "data"} label="View data" onClick={() => toggle("data")} />
          )}
          {message.sql && (
            <EvidenceToggle isOpen={openSection === "sql"} label="View SQL" onClick={() => toggle("sql")} />
          )}
          {message.error_message && (
            <EvidenceToggle isOpen={openSection === "error"} label="View details" onClick={() => toggle("error")} />
          )}
        </div>

        {openSection === "data" && <ResultTable rows={rows} />}
        {openSection === "sql" && message.sql && (
          <div className="mt-2">
            <SqlBlock sql={message.sql} />
          </div>
        )}
        {openSection === "error" && message.error_message && (
          <p className="mt-2 rounded-md border border-danger/20 bg-danger/5 p-3 text-xs text-danger">
            {message.error_message}
          </p>
        )}
      </div>
    </div>
  );
}
