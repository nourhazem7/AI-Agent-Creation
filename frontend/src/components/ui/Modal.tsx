import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  footer?: ReactNode;
}

export function Modal({ isOpen, onClose, title, children, footer }: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  // Callers pass onClose inline (e.g. onClose={() => setIsOpen(false)}), which is a new
  // function on every render of the caller — completely normal React usage that this effect
  // must not require the caller to memoize. Reading the latest onClose through a ref (rather
  // than putting it in the dependency array) keeps the effect's re-run condition tied to what
  // it's actually supposed to react to: isOpen transitioning, not the parent re-rendering for
  // any other reason (e.g. every keystroke in a field the modal contains).
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!isOpen) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onCloseRef.current();
    }
    document.addEventListener("keydown", handleKeyDown);

    dialogRef.current?.focus();

    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  if (!isOpen) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        className="absolute inset-0"
        aria-hidden="true"
        onClick={onClose}
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className="relative z-10 w-full max-w-md rounded-lg border border-border bg-surface p-6 shadow-card focus:outline-none"
      >
        {title && <h2 className="text-base font-semibold text-ink">{title}</h2>}
        <div className={title ? "mt-4" : ""}>{children}</div>
        {footer && <div className="mt-6 flex justify-end gap-2">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}
