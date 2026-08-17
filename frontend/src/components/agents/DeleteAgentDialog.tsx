import { useState } from "react";
import { Button, Modal } from "../ui";
import { useDeleteAgent } from "../../hooks/useAgents";
import { useToast } from "../../hooks/useToast";
import { apiErrorMessage } from "../../api/client";

interface DeleteAgentDialogProps {
  agentId: string;
  agentName: string;
  isOpen: boolean;
  onClose: () => void;
  onDeleted?: () => void;
}

export function DeleteAgentDialog({ agentId, agentName, isOpen, onClose, onDeleted }: DeleteAgentDialogProps) {
  const [error, setError] = useState<string | null>(null);
  const deleteAgent = useDeleteAgent();
  const { showToast } = useToast();

  async function handleConfirm() {
    setError(null);
    try {
      await deleteAgent.mutateAsync(agentId);
      showToast(`"${agentName}" was deleted`, "success");
      onClose();
      onDeleted?.();
    } catch (err) {
      setError(apiErrorMessage(err, "Could not delete this agent."));
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Delete this agent?">
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink">
          You're about to delete <span className="font-medium">"{agentName}"</span>. This will
          permanently remove the agent, its database connection, knowledge assets, and all
          conversations. This cannot be undone.
        </p>
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="button" variant="danger" isLoading={deleteAgent.isPending} onClick={handleConfirm}>
            Delete agent
          </Button>
        </div>
      </div>
    </Modal>
  );
}
