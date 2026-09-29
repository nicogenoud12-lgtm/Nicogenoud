// Stat tile: etiqueta en tono apagado, valor con cifras proporcionales, detalle opcional.
export default function KpiCard({ label, value, sub, tone = "neutral", hero = false }) {
  const toneClass =
    tone === "positive" ? "text-success" : tone === "negative" ? "text-danger" : "text-text";
  return (
    <div className="card p-4 sm:p-5 min-w-0 h-full">
      <div className="label truncate" title={typeof label === "string" ? label : undefined}>
        {label}
      </div>
      {/* Los montos nunca se parten en dos líneas: si no entran, se recortan con el valor completo en el title */}
      <div
        className={`mt-2 font-semibold tracking-tight leading-tight whitespace-nowrap truncate ${toneClass} ${
          hero ? "text-[32px] sm:text-[40px]" : "text-[19px] sm:text-[22px]"
        }`}
        title={typeof value === "string" ? value : undefined}
      >
        {value}
      </div>
      {sub != null && <div className="text-xs text-textMuted mt-2 truncate">{sub}</div>}
    </div>
  );
}
