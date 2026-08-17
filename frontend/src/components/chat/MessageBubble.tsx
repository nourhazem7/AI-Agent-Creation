import { Badge } from "../ui";
import { SqlDisclosure } from "../shared/SqlDisclosure";
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
    <div className="mt-3 overflow-x-auto rounded-md border border-border">
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

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const rows = message.response_type === "table" ? parseResultRows(message.result_data) : [];

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
        {message.error_message ? (
          <div className="flex flex-col gap-1">
            <Badge tone="danger">Error</Badge>
            <p className="text-sm text-ink">{message.content}</p>
            <p className="text-xs text-danger">{message.error_message}</p>
          </div>
        ) : (
          <p className="whitespace-pre-wrap text-sm text-ink">{message.content}</p>
        )}

        <ResultTable rows={rows} />
        {message.sql && <SqlDisclosure sql={message.sql} />}
      </div>
    </div>
  );
}
