interface TabItem {
  value: string;
  label: string;
}

interface TabsProps {
  items: TabItem[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export function Tabs({ items, value, onChange, className = "" }: TabsProps) {
  return (
    <div role="tablist" className={`inline-flex gap-1 rounded-md border border-border bg-canvas p-1 ${className}`}>
      {items.map((item) => {
        const isActive = item.value === value;
        return (
          <button
            key={item.value}
            role="tab"
            type="button"
            aria-selected={isActive}
            onClick={() => onChange(item.value)}
            className={`rounded px-3 py-1.5 text-sm font-medium transition-colors
              ${isActive ? "bg-surface text-ink shadow-subtle" : "text-ink-muted hover:text-ink"}`}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
