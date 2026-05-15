import { useUiStore } from "../store/uiStore";

export default function CurrencyToggle() {
  const { currency, setCurrency } = useUiStore();
  return (
    <div className="inline-flex rounded-lg bg-surfaceAlt border border-border p-0.5 text-xs">
      {["ARS", "USD"].map((c) => (
        <button
          key={c}
          onClick={() => setCurrency(c)}
          className={`px-3 py-1.5 rounded-md transition ${
            currency === c
              ? "bg-accent text-white"
              : "text-textMuted hover:text-text"
          }`}
        >
          {c}
        </button>
      ))}
    </div>
  );
}
