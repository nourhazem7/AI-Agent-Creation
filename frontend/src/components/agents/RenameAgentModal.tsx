import { useState, type FormEvent } from "react";
import { Button, Input, Modal } from "../ui";
import { useUpdateAgent } from "../../hooks/useAgents";
import { useToast } from "../../hooks/useToast";
import { apiErrorMessage } from "../../api/client";

interface RenameAgentModalProps {
  agentId: string;
  currentName: string;
  isOpen: boolean;
  onClose: () => void;
}

export function RenameAgentModal({ agentId, currentName, isOpen, onClose }: RenameAgentModalProps) {
  const [name, setName] = useState(currentName);
  const [error, setError] = useState<string | null>(null);
  const updateAgent = useUpdateAgent(agentId);
  const { showToast } = useToast();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setError(null);
    try {
      await updateAgent.mutateAsync({ name: trimmed });
      showToast("Agent renamed", "success");
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err, "Could not rename this agent."));
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Rename agent">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          label="Agent name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
          required
        />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" isLoading={updateAgent.isPending} disabled={!name.trim()}>
            Save
          </Button>
        </div>
      </form>
    </Modal>
  );
}
