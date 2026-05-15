export default function KpiCard({ label, value, sub, tone = "neutral" }) {
  const toneClass =
    tone === "positive"
      ? "text-success"
      : tone === "negative"
        ? "text-danger"
        : "text-text";
  return (
    <div className="card p-4 min-w-0">
      <div className="label">{label}</div>
      <div
        className={`mt-1 font-semibold tabular-nums break-words leading-tight ${toneClass}`}
        style={{ fontSize: "clamp(1rem, 4.2vw, 1.5rem)" }}
      >
        {value}
      </div>
      {sub != null && (
        <div className="text-xs text-textMuted mt-1 break-words">{sub}</div>
      )}
    </div>
  );
}
