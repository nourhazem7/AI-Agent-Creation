import { Badge, Card } from "../ui";
import { DIALECTS, type DialectMeta } from "../../lib/dialects";

interface DialectSelectorProps {
  onSelect: (dialect: DialectMeta) => void;
}

export function DialectSelector({ onSelect }: DialectSelectorProps) {
  return (
    <div>
      <h2 className="text-lg font-semibold text-ink">Where does your data live?</h2>
      <p className="mt-1 text-sm text-ink-muted">Choose your database type to continue.</p>

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {DIALECTS.map((dialect) => (
          <Card
            key={dialect.value}
            interactive={dialect.enabled}
            onClick={dialect.enabled ? () => onSelect(dialect) : undefined}
            className={`flex flex-col items-center gap-2 p-5 text-center
              ${dialect.enabled ? "" : "cursor-not-allowed opacity-50"}`}
          >
            <span
              className={`flex h-10 w-10 items-center justify-center rounded-lg text-sm font-semibold text-white ${dialect.color}`}
              aria-hidden="true"
            >
              {dialect.initial}
            </span>
            <span className="text-sm font-medium text-ink">{dialect.label}</span>
            {!dialect.enabled && <Badge tone="neutral">Coming soon</Badge>}
          </Card>
        ))}
      </div>
    </div>
  );
}
