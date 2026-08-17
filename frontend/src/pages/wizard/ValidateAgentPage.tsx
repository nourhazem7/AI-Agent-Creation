import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Button, Card, Tabs } from "../../components/ui";
import { TestCard } from "../../components/validation/TestCard";
import { AddTestModal } from "../../components/validation/AddTestModal";
import { useAgent } from "../../hooks/useAgents";
import {
  useRunAllValidationTests,
  useRunFailedValidationTests,
  useValidationSummary,
  useValidationTests,
} from "../../hooks/useValidation";
import { useGenerateAsset } from "../../hooks/useKnowledgeAssets";
import { withMinDuration } from "../../lib/withMinDuration";
import { apiErrorMessage } from "../../api/client";
import type { RunStatus } from "../../api/validation";

type Filter = "all" | "passed" | "failed" | "not_run";

export default function ValidateAgentPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: agent } = useAgent(agentId);
  const { data: tests, isLoading, isError, error } = useValidationTests(agentId ?? "");
  const { data: summary } = useValidationSummary(agentId ?? "");
  const generateAsset = useGenerateAsset(agentId ?? "");
  const runAll = useRunAllValidationTests(agentId ?? "");
  const runFailed = useRunFailedValidationTests(agentId ?? "");

  const [filter, setFilter] = useState<Filter>("all");
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const filtered = useMemo(() => {
    if (!tests) return [];
    if (filter === "all") return tests;
    const wanted: RunStatus = filter === "not_run" ? "not_run" : filter === "passed" ? "passed" : "failed";
    return tests.filter((t) => (wanted === "failed" ? t.last_status === "failed" || t.last_status === "error" : t.last_status === wanted));
  }, [tests, filter]);

  if (!agentId) return null;

  async function handleGenerate() {
    setActionError(null);
    try {
      const result = await withMinDuration(generateAsset.mutateAsync("validation_suite"), 900);
      if (result.status === "error") {
        setActionError(result.error_message ?? "Could not generate test cases.");
      } else {
        queryClient.invalidateQueries({ queryKey: ["validation-tests", agentId] });
        queryClient.invalidateQueries({ queryKey: ["validation-summary", agentId] });
      }
    } catch (err) {
      setActionError(apiErrorMessage(err, "Could not generate test cases."));
    }
  }

  async function handleRunAll() {
    setActionError(null);
    try {
      await withMinDuration(runAll.mutateAsync());
    } catch (err) {
      setActionError(apiErrorMessage(err, "Could not run all tests."));
    }
  }

  async function handleRunFailed() {
    setActionError(null);
    try {
      await withMinDuration(runFailed.mutateAsync());
    } catch (err) {
      setActionError(apiErrorMessage(err, "Could not run failed tests."));
    }
  }

  const hasTests = (tests?.length ?? 0) > 0;
  const hasFailures = (summary?.failed ?? 0) + (summary?.error ?? 0) > 0;
  const totalWithExpectation = tests?.filter((t) => t.expected_answer || t.expected_sql).length ?? 0;

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink">Test your agent</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Prove {agent?.name ?? "this agent"} understands your database before relying on it in Chat.
          </p>
        </div>
        {hasTests && (
          <div className="flex shrink-0 items-center gap-2">
            <Button variant="secondary" size="sm" onClick={() => setIsAddOpen(true)}>
              + Add test case
            </Button>
            <Button
              variant="secondary"
              size="sm"
              isLoading={runFailed.isPending}
              disabled={!hasFailures}
              onClick={handleRunFailed}
            >
              Run failed
            </Button>
            <Button size="sm" isLoading={runAll.isPending} onClick={handleRunAll}>
              Run all
            </Button>
          </div>
        )}
      </div>

      {summary && hasTests && (
        <Card className="mt-6 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm text-ink">
              Validation coverage:{" "}
              <span className="font-medium">
                {summary.passed}/{summary.total} passed
              </span>
              {totalWithExpectation > 0 && (
                <span className="text-ink-muted">
                  {" "}
                  ({totalWithExpectation} test{totalWithExpectation === 1 ? "" : "s"} with a defined expectation)
                </span>
              )}
            </div>
            <div className="flex gap-4 text-xs text-ink-muted">
              <span>{summary.passed} passed</span>
              <span>{summary.failed} failed</span>
              <span>{summary.error} error</span>
              <span>{summary.not_run} not run</span>
            </div>
          </div>
        </Card>
      )}

      {isLoading && (
        <div className="mt-10 flex justify-center">
          <span className="h-6 w-6 animate-spin rounded-full border-2 border-ink border-t-transparent" />
        </div>
      )}

      {isError && (
        <p className="mt-6 rounded-md border border-danger/20 bg-danger/5 px-4 py-3 text-sm text-danger">
          Couldn't load validation tests: {apiErrorMessage(error)}
        </p>
      )}

      {actionError && (
        <p className="mt-4 rounded-md border border-danger/20 bg-danger/5 px-4 py-3 text-sm text-danger">
          {actionError}
        </p>
      )}

      {!isLoading && !hasTests && (
        <div className="mt-10 flex flex-col items-center gap-4 rounded-lg border border-dashed border-border py-16 text-center">
          <p className="text-sm text-ink-muted">
            No test questions yet. Generate some from your validation suite, or add your own.
          </p>
          <div className="flex gap-2">
            <Button isLoading={generateAsset.isPending} onClick={handleGenerate}>
              Generate test cases
            </Button>
            <Button variant="secondary" onClick={() => setIsAddOpen(true)}>
              + Add test case
            </Button>
          </div>
        </div>
      )}

      {hasTests && (
        <>
          <Tabs
            className="mt-6"
            items={[
              { value: "all", label: "All" },
              { value: "passed", label: "Passed" },
              { value: "failed", label: "Failed" },
              { value: "not_run", label: "Not run" },
            ]}
            value={filter}
            onChange={(v) => setFilter(v as Filter)}
          />

          <div className="mt-4 flex flex-col gap-3">
            {filtered.map((test) => (
              <TestCard key={test.id} agentId={agentId} test={test} />
            ))}
            {filtered.length === 0 && (
              <p className="py-8 text-center text-sm text-ink-muted">No tests match this filter.</p>
            )}
          </div>

          <div className="mt-8 flex justify-end">
            <Button onClick={() => navigate(`/agents/${agentId}/chat`)}>Start chatting with this agent</Button>
          </div>
        </>
      )}

      <AddTestModal agentId={agentId} isOpen={isAddOpen} onClose={() => setIsAddOpen(false)} />
    </div>
  );
}
