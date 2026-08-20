import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Card } from "../components/ui/Card";
import { useAuth } from "../hooks/useAuth";
import { apiErrorMessage } from "../api/client";

function BrandMark({ size = 18, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      aria-hidden="true"
      className={`shrink-0 ${className}`}
    >
      <rect x="2.5" y="10.5" width="3.4" height="7" rx="0.8" fill="currentColor" />
      <rect x="8.3" y="6.5" width="3.4" height="11" rx="0.8" fill="currentColor" />
      <rect x="14.1" y="2.5" width="3.4" height="15" rx="0.8" fill="currentColor" />
    </svg>
  );
}

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login({ email, password });
      navigate("/", { replace: true });
    } catch (err) {
      setError(apiErrorMessage(err, "Could not sign in. Check your email and password."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen bg-canvas">
      {/* Brand panel — hidden below md so mobile goes straight to the form, never a scroll
          detour through decorative content. */}
      <div className="relative hidden overflow-hidden bg-[#25272B] md:flex md:w-2/5 md:flex-col md:justify-between md:px-12 md:py-14 lg:w-1/2 lg:px-16">
        <svg
          className="pointer-events-none absolute inset-0 h-full w-full text-white opacity-[0.1]"
          viewBox="0 0 400 600"
          preserveAspectRatio="xMidYMid slice"
          fill="none"
          aria-hidden="true"
        >
          <g stroke="currentColor" strokeWidth="1">
            <line x1="60" y1="80" x2="180" y2="140" />
            <line x1="180" y1="140" x2="320" y2="90" />
            <line x1="180" y1="140" x2="140" y2="260" />
            <line x1="140" y1="260" x2="300" y2="300" />
            <line x1="300" y1="300" x2="340" y2="440" />
            <line x1="140" y1="260" x2="60" y2="380" />
            <line x1="60" y1="380" x2="180" y2="480" />
            <line x1="180" y1="480" x2="330" y2="520" />
          </g>
          <g fill="currentColor">
            <circle cx="60" cy="80" r="4" />
            <circle cx="180" cy="140" r="5" />
            <circle cx="320" cy="90" r="4" />
            <circle cx="140" cy="260" r="5" />
            <circle cx="300" cy="300" r="4" />
            <circle cx="340" cy="440" r="4" />
            <circle cx="60" cy="380" r="4" />
            <circle cx="180" cy="480" r="5" />
            <circle cx="330" cy="520" r="4" />
          </g>
        </svg>

        <div className="relative flex items-center gap-2.5">
          <BrandMark size={28} className="text-white" />
          <span className="text-2xl font-semibold tracking-tight text-white">AgentForge</span>
        </div>

        <div className="relative max-w-md">
          <h1 className="text-3xl font-semibold leading-tight text-white">
            Turn your company's data into answers.
          </h1>
          <p className="mt-4 text-base text-white/70">
            Build trusted AI agents that understand your business database and answer questions with
            confidence.
          </p>
        </div>

        <p className="relative text-xs text-white/40">© {new Date().getFullYear()} AgentForge</p>
      </div>

      {/* Sign-in form */}
      <div className="flex flex-1 flex-col items-center justify-center px-4 py-12 sm:px-6">
        <div className="mb-8 flex items-center gap-2 md:hidden">
          <BrandMark className="text-ink" />
          <span className="text-sm font-semibold tracking-tight text-ink">AgentForge</span>
        </div>

        <Card className="w-full max-w-sm p-8">
          <h2 className="text-xl font-semibold text-ink">Sign in to AgentForge</h2>
          <p className="mt-1.5 text-sm text-ink-muted">Access your company's analytics workspace.</p>

          <form onSubmit={handleSubmit} className="mt-7 flex flex-col gap-4">
            <Input
              label="Work email"
              type="email"
              name="email"
              autoComplete="email"
              placeholder="owner@acmecorp.io"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Input
              label="Password"
              type="password"
              name="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />

            {error && <p className="text-sm text-danger">{error}</p>}

            <Button type="submit" isLoading={isSubmitting} size="lg" className="mt-2 w-full">
              Sign in
            </Button>
          </form>

          <p className="mt-7 text-center text-sm text-ink-muted">
            New to AgentForge?{" "}
            <Link to="/register" className="font-medium text-ink hover:underline underline-offset-2">
              Create your company account
            </Link>
          </p>
        </Card>
      </div>
    </div>
  );
}
