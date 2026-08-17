import { useEffect, useRef, useState } from "react";

interface AgentActionsMenuProps {
  onRename: () => void;
  onDelete: () => void;
}

export function AgentActionsMenu({ onRename, onDelete }: AgentActionsMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsOpen((v) => !v);
        }}
        aria-label="Agent actions"
        aria-haspopup="menu"
        aria-expanded={isOpen}
        className="flex h-7 w-7 items-center justify-center rounded-md text-ink-muted hover:bg-canvas hover:text-ink"
      >
        <span aria-hidden="true">⋮</span>
      </button>

      {isOpen && (
        <div
          role="menu"
          className="absolute right-0 top-8 z-10 w-36 overflow-hidden rounded-md border border-border bg-surface shadow-card"
        >
          <button
            type="button"
            role="menuitem"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setIsOpen(false);
              onRename();
            }}
            className="block w-full px-3 py-2 text-left text-sm text-ink hover:bg-canvas"
          >
            Rename
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setIsOpen(false);
              onDelete();
            }}
            className="block w-full px-3 py-2 text-left text-sm text-danger hover:bg-danger/5"
          >
            Delete
          </button>
        </div>
      )}
    </div>
  );
}
