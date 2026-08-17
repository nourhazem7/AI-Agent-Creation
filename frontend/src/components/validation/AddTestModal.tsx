import { useState } from "react";
import { Button, Modal } from "../ui";
import { apiErrorMessage } from "../../api/client";
import { useCreateValidationTest } from "../../hooks/useValidation";

interface AddTestModalProps {
  agentId: string;
  isOpen: boolean;
  onClose: () => void;
}

const textareaClass =
  "rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-muted " +
  "focus:outline-none focus:ring-2 focus:ring-ink/20";

export function AddTestModal({ agentId, isOpen, onClose }: AddTestModalProps) {
  const createTest = useCreateValidationTest(agentId);
  const [question, setQuestion] = useState("");
  const [criteria, setCriteria] = useState("");
  const [expectedAnswer, setExpectedAnswer] = useState("");
  const [expectedSql, setExpectedSql] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setQuestion("");
    setCriteria("");
    setExpectedAnswer("");
    setExpectedSql("");
    setShowAdvanced(false);
    setError(null);
  }

  function handleClose() {
    reset();
    onClose();
  }

  async function handleSubmit() {
    setError(null);
    if (!question.trim()) {
      setError("Enter a question to test.");
      return;
    }
    try {
      await createTest.mutateAsync({
        question: question.trim(),
        criteria: criteria.trim() || undefined,
        expected_answer: expectedAnswer.trim() || undefined,
        expected_sql: expectedSql.trim() || undefined,
      });
      handleClose();
    } catch (err) {
      setError(apiErrorMessage(err, "Could not add this test."));
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Add a test question"
      footer={
        <>
          <Button variant="secondary" onClick={handleClose}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} isLoading={createTest.isPending}>
            Add test
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-muted">
          Ask a question the way you'd ask a colleague — no SQL knowledge required.
        </p>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="test-question" className="text-sm font-medium text-ink">
            Question
          </label>
          <textarea
            id="test-question"
            rows={2}
            className={textareaClass}
            placeholder="e.g. Which sales rep generated the most revenue this year?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="test-criteria" className="text-sm font-medium text-ink">
            Correctness requirement <span className="font-normal text-ink-muted">(optional)</span>
          </label>
          <textarea
            id="test-criteria"
            rows={2}
            className={textareaClass}
            placeholder="What must be true for the answer to be correct? e.g. Must restrict to the Enterprise segment and include exactly Credit Card and Bank Transfer totals."
            value={criteria}
            onChange={(e) => setCriteria(e.target.value)}
          />
          <p className="text-xs text-ink-muted">
            If you set this, it's treated as a hard requirement when grading the agent's answer.
          </p>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="test-expected-answer" className="text-sm font-medium text-ink">
            Example answer <span className="font-normal text-ink-muted">(optional)</span>
          </label>
          <textarea
            id="test-expected-answer"
            rows={2}
            className={textareaClass}
            placeholder="An example of what the answer might look like — used only as a hint, not graded literally."
            value={expectedAnswer}
            onChange={(e) => setExpectedAnswer(e.target.value)}
          />
        </div>

        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          className="self-start text-xs font-medium text-ink-muted hover:text-ink"
        >
          {showAdvanced ? "Hide advanced (SQL) option" : "Advanced: add a reference SQL solution"}
        </button>

        {showAdvanced && (
          <div className="flex flex-col gap-1.5">
            <label htmlFor="test-expected-sql" className="text-sm font-medium text-ink">
              Reference SQL <span className="font-normal text-ink-muted">(optional, for technical users)</span>
            </label>
            <textarea
              id="test-expected-sql"
              rows={3}
              className={`${textareaClass} font-mono`}
              placeholder="SELECT ..."
              value={expectedSql}
              onChange={(e) => setExpectedSql(e.target.value)}
            />
            <p className="text-xs text-ink-muted">
              This will be run against your database right now to make sure it's valid. It's shown
              as one possible solution for diagnostic reference — the agent isn't required to match
              it exactly.
            </p>
          </div>
        )}

        {error && (
          <p className="rounded-md border border-danger/20 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</p>
        )}
      </div>
    </Modal>
  );
}
