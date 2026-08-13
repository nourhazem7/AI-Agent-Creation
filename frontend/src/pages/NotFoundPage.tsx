import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-canvas text-center">
      <h1 className="text-2xl font-semibold text-ink">Page not found</h1>
      <p className="text-sm text-ink-muted">The page you're looking for doesn't exist.</p>
      <Link to="/" className="text-sm font-medium text-ink underline underline-offset-2">
        Back to dashboard
      </Link>
    </div>
  );
}
