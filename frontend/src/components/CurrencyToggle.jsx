import { useUiStore } from "../store/uiStore";

export default function CurrencyToggle() {
  const { currency, setCurrency } = useUiStore();
  return (
    <div className="segmented" role="group" aria-label="Moneda">
      {["ARS", "USD"].map((c) => (
        <button
          key={c}
          onClick={() => setCurrency(c)}
          aria-pressed={currency === c}
          className={`segmented-item ${currency === c ? "segmented-item-active" : ""}`}
        >
          {c}
        </button>
      ))}
    </div>
  );
}
