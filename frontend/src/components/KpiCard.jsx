export default function KpiCard({ label, value, sub, tone = "neutral" }) {
  const toneClass =
    tone === "positive"
      ? "text-success"
      : tone === "negative"
        ? "text-danger"
        : "text-text";
  return (
    <div className="card p-4">
      <div className="label">{label}</div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${toneClass}`}>
        {value}
      </div>
      {sub != null && (
        <div className="text-xs text-textMuted mt-1">{sub}</div>
      )}
    </div>
  );
}
