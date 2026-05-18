import { PERIODS } from "../../utils/periods";

export default function PeriodFilter({ value, onChange }) {
  return (
    <div className="flex gap-0.5">
      {PERIODS.map((p) => (
        <button
          key={p.label}
          onClick={() => onChange(p.label)}
          title={p.title}
          className={`px-1.5 py-0.5 text-xs rounded transition-colors ${
            value === p.label
              ? "bg-accent/15 text-accent font-semibold"
              : "text-textMuted hover:text-text hover:bg-surfaceAlt"
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}
