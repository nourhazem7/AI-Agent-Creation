import { useState } from "react";
import { Button, Modal } from "../ui";
import { apiErrorMessage } from "../../api/client";
import { useCreateAgentMemory } from "../../hooks/useAgentMemory";

interface AddBusinessRuleModalProps {
  agentId: string;
  isOpen: boolean;
  onClose: () => void;
}

export function AddBusinessRuleModal({ agentId, isOpen, onClose }: AddBusinessRuleModalProps) {
  const createMemory = useCreateAgentMemory(agentId);
  const [content, setContent] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleClose() {
    setContent("");
    setError(null);
    onClose();
  }

  async function handleSave() {
    setError(null);
    if (!content.trim()) {
      setError("Enter a rule before saving.");
      return;
    }
    try {
      await createMemory.mutateAsync(content.trim());
      handleClose();
    } catch (err) {
      setError(apiErrorMessage(err, "Could not save this rule."));
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Add business rule"
      footer={
        <>
          <Button variant="secondary" onClick={handleClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} isLoading={createMemory.isPending}>
            Save rule
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-sm text-ink-muted">
          Add a rule or definition that should apply to future questions.
        </p>
        <textarea
          rows={3}
          autoFocus
          className="rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink
            placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-ink/20"
          placeholder="e.g. Revenue excludes cancelled orders."
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
        {error && <p className="text-sm text-danger">{error}</p>}
      </div>
    </Modal>
  );
}
