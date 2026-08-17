import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Badge, Button, Card } from "../../components/ui";
import { useAgent } from "../../hooks/useAgents";
import { useKnowledgeSummary } from "../../hooks/useKnowledgeSummary";
import { apiErrorMessage } from "../../api/client";
import type { TableFact } from "../../api/knowledgeSummary";

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-border bg-canvas px-4 py-3">
      <div className="text-2xl font-semibold text-ink">{value}</div>
      <div className="text-xs text-ink-muted">{label}</div>
    </div>
  );
}

function SectionHeading({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div className="mb-4">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">{eyebrow}</p>
      <h2 className="text-base font-semibold text-ink">{title}</h2>
    </div>
  );
}

function TableRow({ table }: { table: TableFact }) {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <div className="border-b border-border last:border-b-0">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm hover:bg-canvas"
      >
        <span className="font-medium text-ink">{table.name}</span>
        <span className="text-xs text-ink-muted">
          {table.columns.length} column{table.columns.length === 1 ? "" : "s"}
          {table.foreign_keys.length > 0 ? ` · ${table.foreign_keys.length} relationship${table.foreign_keys.length === 1 ? "" : "s"}` : ""}
        </span>
      </button>
      {isOpen && (
        <div className="bg-canvas px-4 py-3">
          <ul className="flex flex-col gap-1 text-xs">
            {table.columns.map((col) => (
              <li key={col.name} className="flex items-center gap-2 text-ink-muted">
                <span className="font-mono text-ink">{col.name}</span>
                <span>{col.type}</span>
                {col.is_primary_key && <Badge tone="accent">Primary key</Badge>}
                {!col.nullable && <span className="text-ink-muted">NOT NULL</span>}
              </li>
            ))}
          </ul>
          {table.foreign_keys.length > 0 && (
            <div className="mt-2 flex flex-col gap-1 text-xs text-ink-muted">
              {table.foreign_keys.map((fk, i) => (
                <div key={i}>
                  {fk.columns.join(", ")} → <span className="text-ink">{fk.referred_table}</span>(
                  {fk.referred_columns.join(", ")})
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function KnowledgeSummaryPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const { data: agent } = useAgent(agentId);
  const { data: summary, isLoading, isError, error } = useKnowledgeSummary(agentId ?? "");
  const [docExpanded, setDocExpanded] = useState(false);

  if (!agentId) return null;

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-xl font-semibold text-ink">Knowledge Summary</h1>
      <p className="mt-1 text-sm text-ink-muted">
        What {agent?.name ?? "this agent"} currently knows about your database.
      </p>

      {isLoading && (
        <div className="mt-10 flex justify-center">
          <span className="h-6 w-6 animate-spin rounded-full border-2 border-ink border-t-transparent" />
        </div>
      )}

      {isError && (
        <p className="mt-6 rounded-md border border-danger/20 bg-danger/5 px-4 py-3 text-sm text-danger">
          Couldn't load the knowledge summary: {apiErrorMessage(error)}
        </p>
      )}

      {summary && (
        <div className="mt-6 flex flex-col gap-6">
          {/* Readiness banner */}
          <div
            className={`flex items-center justify-between rounded-lg border px-4 py-3 text-sm ${
              summary.readiness.all_ready
                ? "border-success/20 bg-success/10 text-success"
                : "border-warning/20 bg-warning/10 text-warning"
            }`}
          >
            <span>
              {summary.readiness.all_ready
                ? "All knowledge assets are ready."
                : `${summary.readiness.ready_count}/${summary.readiness.total_count} knowledge assets ready.`}
            </span>
          </div>

          {/* 1. Verified from the database */}
          <Card className="p-5">
            <SectionHeading
              eyebrow="Verified directly from your database"
              title="Schema &amp; relationships"
            />
            {!summary.database.connected && summary.database.source === "stored_schema_asset" && (
              <p className="mb-3 text-xs text-warning">
                Showing the last saved schema — the database isn't connected right now, so this
                couldn't be re-checked live.
              </p>
            )}
            {summary.database.connected && summary.database.schema_asset_matches_live === false && (
              <p className="mb-3 text-xs text-warning">
                Your saved schema asset no longer matches the live database. Consider
                regenerating it from Knowledge Assets.
              </p>
            )}
            {!summary.database.connected && summary.database.source === "none" && (
              <p className="text-sm text-ink-muted">No database connected yet.</p>
            )}
            {summary.database.table_count > 0 && (
              <>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-2">
                  <StatTile label="Tables" value={summary.database.table_count} />
                  <StatTile label="Relationships" value={summary.database.relationship_count} />
                </div>
                <div className="mt-4 overflow-hidden rounded-md border border-border">
                  {summary.database.tables.map((table) => (
                    <TableRow key={table.name} table={table} />
                  ))}
                </div>
              </>
            )}
          </Card>

          {/* 2. From documentation */}
          <Card className="p-5">
            <SectionHeading eyebrow="From your documentation asset" title="Business context" />
            {!summary.documentation.configured && (
              <p className="text-sm text-ink-muted">No documentation configured yet.</p>
            )}
            {summary.documentation.configured && (
              <>
                <div className="mb-3 flex items-center gap-2">
                  <Badge tone={summary.documentation.status === "ready" ? "success" : "danger"}>
                    {summary.documentation.status}
                  </Badge>
                  <Badge tone="neutral">
                    {summary.documentation.source === "generated" ? "Generated" : "Uploaded"}
                  </Badge>
                  {summary.documentation.verified ? (
                    <Badge tone="success">✓ Verified against database</Badge>
                  ) : (
                    <Badge tone="neutral">Not verified by current pipeline</Badge>
                  )}
                  <span className="text-xs text-ink-muted">{summary.documentation.word_count} words</span>
                </div>
                {summary.documentation.content && (
                  <div className="rounded-md border border-border bg-canvas p-3">
                    <p
                      className={`whitespace-pre-wrap text-sm text-ink ${docExpanded ? "" : "line-clamp-6"}`}
                    >
                      {summary.documentation.content}
                    </p>
                    <button
                      type="button"
                      onClick={() => setDocExpanded((v) => !v)}
                      className="mt-2 text-xs font-medium text-ink-muted hover:text-ink"
                    >
                      {docExpanded ? "Show less" : "Show more"}
                    </button>
                  </div>
                )}
              </>
            )}
          </Card>

          {/* 3. Validation coverage */}
          <Card className="p-5">
            <SectionHeading eyebrow="Validation coverage" title="Test questions ready to verify this agent" />
            {!summary.validation.configured && (
              <p className="text-sm text-ink-muted">No validation suite configured yet.</p>
            )}
            {summary.validation.configured && (
              <div className="grid grid-cols-2 gap-3">
                <StatTile label="Total questions" value={summary.validation.total_tests} />
                <StatTile
                  label="SQL-verified"
                  value={`${summary.validation.sql_verified_count}/${summary.validation.total_tests}`}
                />
              </div>
            )}
          </Card>

          <div className="flex justify-end">
            <Button onClick={() => navigate(`/agents/${agentId}/validate`)}>Continue to Validation</Button>
          </div>
        </div>
      )}
    </div>
  );
}
