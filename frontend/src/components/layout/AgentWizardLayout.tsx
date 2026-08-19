import { Outlet, useLocation } from "react-router-dom";
import { AppShell } from "./AppShell";

const STEPS = [
  { key: "connect", label: "Database" },
  { key: "knowledge", label: "Knowledge" },
  { key: "validate", label: "Validate" },
  { key: "ready", label: "Ready" },
] as const;

// "summary" belongs under the Knowledge step from the user's point of view; "results"
// belongs under Validate.
const STEP_ALIASES: Record<string, (typeof STEPS)[number]["key"]> = {
  summary: "knowledge",
  results: "validate",
};

function currentStepKey(pathname: string): string | null {
  const segment = pathname.split("/").filter(Boolean).pop() ?? "";
  return STEP_ALIASES[segment] ?? segment;
}

export function AgentWizardLayout() {
  const location = useLocation();
  const activeKey = currentStepKey(location.pathname);
  const activeIndex = STEPS.findIndex((s) => s.key === activeKey);

  return (
    <AppShell>
      <div className="border-b border-border bg-surface">
        <ol className="mx-auto flex max-w-3xl items-center gap-2 px-6 py-4">
          {STEPS.map((step, index) => {
            const isDone = activeIndex >= 0 && index < activeIndex;
            const isActive = index === activeIndex;
            return (
              <li key={step.key} className="flex flex-1 items-center gap-2">
                <span
                  className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-medium
                    ${isActive ? "bg-ink text-white" : isDone ? "bg-ink/10 text-ink" : "bg-canvas text-ink-muted border border-border"}`}
                  aria-current={isActive ? "step" : undefined}
                >
                  {index + 1}
                </span>
                <span className={`text-sm ${isActive ? "font-medium text-ink" : "text-ink-muted"}`}>
                  {step.label}
                </span>
                {index < STEPS.length - 1 && <span className="h-px flex-1 bg-border" aria-hidden="true" />}
              </li>
            );
          })}
        </ol>
      </div>
      <Outlet />
    </AppShell>
  );
}
