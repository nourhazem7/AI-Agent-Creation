import { useState } from "react";
import { Badge, Button } from "../ui";
import { SqlDisclosure } from "../shared/SqlDisclosure";
import { withMinDuration } from "../../lib/withMinDuration";
import { apiErrorMessage } from "../../api/client";
import { useDeleteValidationTest, useRunValidationTest } from "../../hooks/useValidation";
import type { ValidationTest } from "../../api/validation";

const STATUS_META: Record<ValidationTest["last_status"], { label: string; tone: "neutral" | "success" | "warning" | "danger" }> = {
  not_run: { label: "Not run", tone: "neutral" },
  passed: { label: "Passed", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  error: { label: "Error", tone: "warning" },
};

const ORIGIN_LABEL: Record<ValidationTest["origin"], string> = {
  ai_generated: "AI-generated",
  user_created: "Your test",
  uploaded: "Uploaded",
};

function parseRows(json: string | null): Record<string, unknown>[] {
  if (!json) return [];
  try {
    const parsed = JSON.parse(json);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function ResultTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (rows.length === 0) return <p className="text-xs text-ink-muted">No rows returned.</p>;
  const columns = Object.keys(rows[0]);
  const shown = rows.slice(0, 10);
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-left text-xs">
        <thead className="bg-canvas text-ink-muted">
          <tr>
            {columns.map((col) => (
              <th key={col} className="px-2 py-1.5 font-medium">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((row, i) => (
            <tr key={i} className="border-t border-border">
              {columns.map((col) => (
                <td key={col} className="px-2 py-1.5 text-ink">
                  {String(row[col] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > shown.length && (
        <p className="border-t border-border px-2 py-1 text-[11px] text-ink-muted">
          Showing {shown.length} of {rows.length} rows
        </p>
      )}
    </div>
  );
}

function VerdictBanner({ status, note }: { status: ValidationTest["last_status"]; note: string | null }) {
  if (status === "passed" && note?.startsWith("Exploratory")) {
    return (
      <div className="rounded-md border border-border bg-canvas px-3 py-2">
        <p className="text-sm font-medium text-ink">Ran successfully</p>
        <p className="mt-0.5 text-xs text-ink-muted">{note}</p>
      </div>
    );
  }
  if (status === "passed") {
    return (
      <div className="rounded-md border border-success/20 bg-success/10 px-3 py-2">
        <p className="text-sm font-medium text-success">✓ Passed — results match</p>
        {note && <p className="mt-0.5 text-xs text-ink-muted">{note}</p>}
      </div>
    );
  }
  if (status === "failed") {
    return (
      <div className="rounded-md border border-danger/20 bg-danger/10 px-3 py-2">
        <p className="text-sm font-medium text-danger">✕ Failed — results differ</p>
        {note && <p className="mt-0.5 text-xs text-ink-muted">{note}</p>}
      </div>
    );
  }
  return null;
}

export function TestCard({ agentId, test }: { agentId: string; test: ValidationTest }) {
  const runTest = useRunValidationTest(agentId);
  const deleteTest = useDeleteValidationTest(agentId);
  const [error, setError] = useState<string | null>(null);

  const isRunning = runTest.isPending && runTest.variables === test.id;
  const status = isRunning ? "running" : test.last_status;
  const statusMeta = STATUS_META[test.last_status];
  const run = test.latest_run;

  const agentRows = parseRows(run?.result_data ?? null);
  const referenceRows = parseRows(run?.reference_result ?? null);
  // A reference result is only present when a verified reference SQL was actually executed
  // this run (branch 1) — that's the signal for showing the two-column comparison layout.
  const hasReferenceResult = !!run?.reference_result;
  // Independent of whether the test has run yet — a verified reference SQL always outranks
  // the expected_answer text once one exists, so the label should say so up front.
  const hasVerifiedReferenceSql = !!(test.expected_sql && test.expected_sql_verified);

  async function handleRun() {
    setError(null);
    try {
      await withMinDuration(runTest.mutateAsync(test.id), 700);
    } catch (err) {
      setError(apiErrorMessage(err, "Could not run this test."));
    }
  }

  async function handleDelete() {
    setError(null);
    try {
      await deleteTest.mutateAsync(test.id);
    } catch (err) {
      setError(apiErrorMessage(err, "Could not delete this test."));
    }
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">Question</p>
          <p className="text-sm font-medium text-ink">{test.question}</p>
          <div className="flex flex-wrap items-center gap-1.5">
            {status === "running" ? (
              <Badge tone="warning">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" aria-hidden="true" />
                Running…
              </Badge>
            ) : (
              <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
            )}
            <Badge tone="neutral">{ORIGIN_LABEL[test.origin]}</Badge>
            {test.expected_sql && (
              <Badge tone={test.expected_sql_verified ? "success" : "neutral"}>
                {test.expected_sql_verified ? "Reference SQL verified" : "Reference SQL unverified"}
              </Badge>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="secondary" size="sm" isLoading={status === "running"} onClick={handleRun}>
            {status === "running" ? "Running…" : "Run"}
          </Button>
          {test.origin === "user_created" && (
            <Button variant="ghost" size="sm" onClick={handleDelete} isLoading={deleteTest.isPending}>
              Delete
            </Button>
          )}
        </div>
      </div>

      {test.expected_answer && (
        <p className="mt-2 text-xs text-ink-muted">
          Expected answer{" "}
          <span className="text-ink-muted/70">
            ({hasVerifiedReferenceSql ? "explanatory only — graded against the verified reference SQL, not this text" : "used to grade this test"})
          </span>
          : <span className="text-ink">{test.expected_answer}</span>
        </p>
      )}

      {error && <p className="mt-2 text-xs text-danger">{error}</p>}

      {run && (
        <div className="mt-3 flex flex-col gap-3 border-t border-border pt-3">
          {run.error_message && <p className="text-xs text-danger">{run.error_message}</p>}

          {hasReferenceResult ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">
                    Reference result <span className="normal-case text-ink-muted/70">— correct answer according to the database</span>
                  </p>
                  <ResultTable rows={referenceRows} />
                  {test.expected_sql && <SqlDisclosure sql={test.expected_sql} />}
                </div>
                <div className="flex flex-col gap-1.5">
                  <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">
                    Agent result <span className="normal-case text-ink-muted/70">— answer produced by Agent One</span>
                  </p>
                  <ResultTable rows={agentRows} />
                  {run.generated_sql && <SqlDisclosure sql={run.generated_sql} />}
                </div>
              </div>
              <VerdictBanner status={run.status} note={run.comparison_note} />
            </>
          ) : (
            <>
              <div className="flex flex-col gap-1.5">
                <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">
                  Agent result <span className="normal-case text-ink-muted/70">— answer produced by Agent One</span>
                </p>
                <ResultTable rows={agentRows} />
                {run.generated_sql && <SqlDisclosure sql={run.generated_sql} />}
              </div>
              <VerdictBanner status={run.status} note={run.comparison_note} />
            </>
          )}
        </div>
      )}
    </div>
  );
}
