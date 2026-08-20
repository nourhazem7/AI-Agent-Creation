import { useState } from "react";
import { Badge, Button } from "../ui";
import { SqlBlock } from "../shared/SqlDisclosure";
import { EvidenceToggle } from "../shared/EvidenceToggle";
import { withMinDuration } from "../../lib/withMinDuration";
import { apiErrorMessage } from "../../api/client";
import { useDeleteValidationTest, useRunValidationTest } from "../../hooks/useValidation";
import type { ValidationTest } from "../../api/validation";

const STATUS_META: Record<
  ValidationTest["last_status"],
  { label: string; tone: "neutral" | "success" | "warning" | "danger" }
> = {
  not_run: { label: "Not run", tone: "neutral" },
  passed: { label: "Passed", tone: "success" },
  partial: { label: "Partial", tone: "warning" },
  failed: { label: "Failed", tone: "danger" },
  error: { label: "Error", tone: "warning" },
  inconclusive: { label: "Inconclusive", tone: "neutral" },
};

// origin is persisted per test at creation time (validation_service._sync_from_knowledge_asset
// / create_user_test) and never rewritten afterward — a straight lookup, no need to
// cross-reference the current Knowledge Asset state.
const ORIGIN_LABEL: Record<ValidationTest["origin"], string> = {
  ai_generated: "AI-generated",
  uploaded: "Uploaded",
  manual: "Manual",
};

// A normal employee shouldn't need to understand the judging process to read a verdict —
// these are the only assessment sentences shown by default. The verdict itself (passed/
// partial/failed/error/inconclusive) still comes entirely from the backend; this only
// controls which plain-language sentence accompanies it in the UI.
const ASSESSMENT_META: Record<
  ValidationTest["last_status"],
  { icon: string; label: string; className: string; summary: string } | null
> = {
  not_run: null,
  passed: {
    icon: "✓",
    label: "Passed",
    className: "text-success",
    summary: "The agent answered the question correctly.",
  },
  partial: {
    icon: "◐",
    label: "Partial",
    className: "text-warning",
    summary: "The agent answered most of the question, but some requested information was missing or unclear.",
  },
  failed: {
    icon: "✕",
    label: "Failed",
    className: "text-danger",
    summary: "The agent's answer did not fully satisfy the question.",
  },
  error: {
    icon: "⚠",
    label: "Error",
    className: "text-warning",
    summary: "The agent could not complete this question because an error occurred.",
  },
  inconclusive: {
    icon: "?",
    label: "Inconclusive",
    className: "text-ink-muted",
    summary: "The result could not be confidently evaluated.",
  },
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

// Safety net for the one-line "specific reason" shown under the plain-language verdict: even
// though it's normally sourced from violated_requirement (meant to be a short, answer-specific
// phrase) or this app's own deterministic error messages, never render it if it happens to
// contain internal judging-process language — that's implementation detail, not something a
// normal employee should see.
const BANNED_JUDGE_TERMS = [
  "independent assessment",
  "diagnostic reference",
  "secondary evidence",
  "reference solution",
  "no change from the",
  "authoritative",
];

function isSafeToShow(text: string): boolean {
  const lower = text.toLowerCase();
  return !BANNED_JUDGE_TERMS.some((term) => lower.includes(term));
}

function sentenceCase(text: string): string {
  const words = text.replace(/_/g, " ").toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function pluralize(word: string): string {
  if (/[sxz]$|[cs]h$/i.test(word)) return `${word}es`;
  if (/[^aeiou]y$/i.test(word)) return `${word.slice(0, -1)}ies`;
  return word.toLowerCase().endsWith("s") ? word : `${word}s`;
}

// Best-effort: pick a "*_name" column whose value is unique on every row (e.g.
// "department_name" across 8 one-per-department rows), so a multi-row result can be
// summarized as "8 departments found" instead of a generic count. The uniqueness check is
// what keeps this honest: a join can easily produce 131 rows over only 6 distinct
// project_name values (an employee-per-project-assignment result, not "131 projects"), and
// without checking distinctness that would render as a false quantitative claim. Falls back
// to null — a plain row count — whenever this can't be verified from the data itself.
function guessEntityLabel(rows: Record<string, unknown>[]): string | null {
  const columns = Object.keys(rows[0]);
  const candidates = columns.filter((c) => /_name$/i.test(c) || c.toLowerCase() === "name");
  for (const col of candidates) {
    const distinctValues = new Set(rows.map((r) => JSON.stringify(r[col])));
    if (distinctValues.size !== rows.length) continue; // repeats — not 1:1 with the row count
    const base = col.replace(/_?name$/i, "");
    if (base) return pluralize(base.replace(/_/g, " "));
  }
  return null;
}

// Derives a short, human-readable summary of what the agent's result actually contains —
// never inventing facts, only describing the real row count/columns/values already present
// in result_data. Falls back to a generic sentence whenever a specific summary can't be
// safely derived from the shape of the data alone.
function summarizeAgentResult(rows: Record<string, unknown>[]): string {
  if (rows.length === 0) return "No matching results were found.";

  if (rows.length === 1) {
    const keys = Object.keys(rows[0]);
    if (keys.length === 1) {
      const value = rows[0][keys[0]];
      return `${sentenceCase(keys[0])}: ${value === null || value === undefined ? "—" : String(value)}.`;
    }
    return "1 result found.";
  }

  const entityLabel = guessEntityLabel(rows);
  return entityLabel ? `${rows.length} ${entityLabel} found.` : `${rows.length} results found.`;
}

function ResultTable({ rows }: { rows: Record<string, unknown>[] }) {
  const [expanded, setExpanded] = useState(false);
  if (rows.length === 0) return <p className="text-xs text-ink-muted">No rows returned.</p>;

  const columns = Object.keys(rows[0]);
  const previewCount = 8;
  const shown = expanded ? rows : rows.slice(0, previewCount);

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
      {rows.length > previewCount && (
        <div className="flex items-center justify-between border-t border-border px-2 py-1 text-[11px] text-ink-muted">
          <span>
            Showing {shown.length} of {rows.length} rows
          </span>
          <button type="button" onClick={() => setExpanded((v) => !v)} className="font-medium hover:text-ink">
            {expanded ? "Show fewer" : "View full result"}
          </button>
        </div>
      )}
    </div>
  );
}

type EvidenceSection = "agent-sql" | "agent-result" | "reference" | null;

export function TestCard({ agentId, test }: { agentId: string; test: ValidationTest }) {
  const runTest = useRunValidationTest(agentId);
  const deleteTest = useDeleteValidationTest(agentId);
  const [error, setError] = useState<string | null>(null);
  const [openSection, setOpenSection] = useState<EvidenceSection>(null);
  const [showFullAnswer, setShowFullAnswer] = useState(false);

  const isRunning = runTest.isPending && runTest.variables === test.id;
  const status = isRunning ? "running" : test.last_status;
  const statusMeta = STATUS_META[test.last_status];
  const run = test.latest_run;

  const agentRows = parseRows(run?.result_data ?? null);
  const referenceRows = parseRows(run?.reference_result ?? null);
  const hasReferenceResult = !!run?.reference_result;

  function toggle(section: EvidenceSection) {
    setOpenSection((prev) => (prev === section ? null : section));
  }

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

  const assessmentMeta = run ? ASSESSMENT_META[run.status] : null;
  // A short, specific reason under the generic sentence — only shown when the backend gave
  // us something concise and answer-specific (violated_requirement), or for error runs where
  // comparison_note is always one of this app's own plain deterministic messages (never
  // judge-generated free text). Never renders the raw judge reasoning paragraph here.
  const rawSpecificReason =
    run?.status !== "passed" && run?.violated_requirement
      ? run.violated_requirement
      : run?.status === "error" && run.comparison_note
        ? run.comparison_note
        : null;
  const specificReason = rawSpecificReason && isSafeToShow(rawSpecificReason) ? rawSpecificReason : null;

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p className="text-[11px] font-medium uppercase tracking-wide text-ink-muted">Business question</p>
          <p className="text-sm font-medium text-ink">{test.question}</p>
          {test.criteria && (
            <p className="text-xs text-ink-muted">
              Must: <span className="text-ink">{test.criteria}</span>
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="secondary" size="sm" isLoading={status === "running"} onClick={handleRun}>
            {status === "running" ? "Running…" : run ? "Re-run" : "Run test"}
          </Button>
          {test.origin === "manual" && (
            <Button variant="ghost" size="sm" onClick={handleDelete} isLoading={deleteTest.isPending}>
              Delete
            </Button>
          )}
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {status === "running" ? (
          <Badge tone="warning">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" aria-hidden="true" />
            Running…
          </Badge>
        ) : (
          <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
        )}
        <Badge tone="neutral">{ORIGIN_LABEL[test.origin]}</Badge>
      </div>

      {error && <p className="mt-2 text-xs text-danger">{error}</p>}

      {run && (
        <div className="mt-3 flex flex-col gap-3 border-t border-border pt-3">
          {run.error_message && <p className="text-xs text-danger">{run.error_message}</p>}

          {run.agent_answer && (
            <div>
              <p className="text-[11px] font-medium uppercase tracking-wide text-ink-muted">Agent answer</p>
              <p className="mt-1 text-sm text-ink">
                <span className="text-success">✓</span> Answered successfully — {summarizeAgentResult(agentRows)}
              </p>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
            {run.generated_sql && (
              <EvidenceToggle
                isOpen={openSection === "agent-sql"}
                label="View agent SQL"
                onClick={() => toggle("agent-sql")}
              />
            )}
            <EvidenceToggle
              isOpen={openSection === "agent-result"}
              label="View agent result"
              onClick={() => toggle("agent-result")}
            />
            {hasReferenceResult && (
              <EvidenceToggle
                isOpen={openSection === "reference"}
                label="View diagnostic reference"
                onClick={() => toggle("reference")}
              />
            )}
          </div>

          {openSection === "agent-sql" && run.generated_sql && <SqlBlock sql={run.generated_sql} />}
          {openSection === "agent-result" && (
            <div>
              <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-ink-muted">Agent result</p>
              <ResultTable rows={agentRows} />
              {run.agent_answer && (
                <div className="mt-2">
                  <button
                    type="button"
                    onClick={() => setShowFullAnswer((v) => !v)}
                    className="text-xs font-medium text-ink-muted hover:text-ink"
                  >
                    {showFullAnswer ? "Hide full agent response" : "View full agent response"}
                  </button>
                  {showFullAnswer && (
                    <p className="mt-2 rounded-md border border-border bg-canvas p-3 text-sm text-ink">
                      {run.agent_answer}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
          {openSection === "reference" && (
            <div className="rounded-md border border-dashed border-border p-3">
              <p className="mb-2 text-xs text-ink-muted">
                Reference solution (diagnostic only) — one possible solution, not the official answer.{" "}
                {test.expected_sql_verified ? "Verified against the database." : "Not verified against the database."}
              </p>
              <ResultTable rows={referenceRows} />
              {test.expected_sql && (
                <div className="mt-2">
                  <SqlBlock sql={test.expected_sql} />
                </div>
              )}
              {test.expected_answer && (
                <p className="mt-2 text-xs text-ink-muted">
                  Example answer: <span className="text-ink">{test.expected_answer}</span>
                </p>
              )}
              {run.comparison_note && (
                <p className="mt-2 text-xs text-ink-muted">
                  Judge reasoning <span className="text-ink-muted/70">(technical)</span>: {run.comparison_note}
                </p>
              )}
            </div>
          )}

          {assessmentMeta && (
            <div>
              <p className={`text-sm font-medium ${assessmentMeta.className}`}>
                {assessmentMeta.icon} {assessmentMeta.label}
              </p>
              <p className="mt-0.5 text-xs text-ink-muted">{assessmentMeta.summary}</p>
              {specificReason && <p className="mt-0.5 text-xs text-ink-muted">{specificReason}</p>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
