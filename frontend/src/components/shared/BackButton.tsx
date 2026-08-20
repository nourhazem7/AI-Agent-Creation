import { useNavigate } from "react-router-dom";

// Uses the router's own history stack (navigate(-1)) rather than a hand-maintained map of
// "previous step" routes — one less thing to keep in sync as wizard steps evolve.
export function BackButton() {
  const navigate = useNavigate();

  return (
    <button
      type="button"
      onClick={() => navigate(-1)}
      aria-label="Back"
      className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-border text-ink-muted
        hover:border-ink/20 hover:bg-canvas hover:text-ink"
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  );
}
