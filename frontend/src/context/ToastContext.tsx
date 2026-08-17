import { createContext, useCallback, useState, type ReactNode } from "react";

type ToastTone = "success" | "danger" | "neutral";

interface Toast {
  id: number;
  message: string;
  tone: ToastTone;
}

interface ToastContextValue {
  showToast: (message: string, tone?: ToastTone) => void;
}

export const ToastContext = createContext<ToastContextValue | undefined>(undefined);

let nextId = 0;

const toneClasses: Record<ToastTone, string> = {
  success: "border-success/20 bg-success/10 text-success",
  danger: "border-danger/20 bg-danger/10 text-danger",
  neutral: "border-border bg-surface text-ink",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, tone: ToastTone = "neutral") => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, message, tone }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3500);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            aria-live="polite"
            className={`pointer-events-auto rounded-md border px-4 py-2.5 text-sm shadow-card ${toneClasses[t.tone]}`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
