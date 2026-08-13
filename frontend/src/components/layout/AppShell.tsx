import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { Button } from "../ui";

interface AppShellProps {
  children: ReactNode;
  /** Optional right-aligned content in the header, e.g. an agent's connection status. */
  headerExtra?: ReactNode;
}

export function AppShell({ children, headerExtra }: AppShellProps) {
  const { me, logout } = useAuth();

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-ink focus:px-3 focus:py-2 focus:text-white"
      >
        Skip to content
      </a>

      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-surface px-6">
        <Link to="/" className="text-sm font-semibold tracking-tight text-ink">
          AgentForge
        </Link>

        <div className="flex items-center gap-4">
          {headerExtra}
          <span className="hidden text-sm text-ink-muted sm:inline">{me?.user.email}</span>
          <Button variant="ghost" size="sm" onClick={logout}>
            Sign out
          </Button>
        </div>
      </header>

      <main id="main-content" className="flex-1">
        {children}
      </main>
    </div>
  );
}
