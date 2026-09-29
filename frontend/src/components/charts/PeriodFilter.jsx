import { PERIODS } from "../../utils/periods";

export default function PeriodFilter({ value, onChange }) {
  return (
    <div className="flex gap-0.5" role="group" aria-label="Período">
      {PERIODS.map((p) => (
        <button
          key={p.label}
          onClick={() => onChange(p.label)}
          title={p.title}
          aria-pressed={value === p.label}
          className={`px-2 h-6 text-[11px] font-medium rounded-md transition-colors ${
            value === p.label ? "bg-surfaceAlt text-text" : "text-textMuted hover:text-text"
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}
