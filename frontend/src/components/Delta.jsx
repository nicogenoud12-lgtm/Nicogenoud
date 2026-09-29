// Variación con signo: el color acompaña a un signo explícito, nunca va solo.
export default function Delta({ value, suffix = "%", digits = 2, className = "" }) {
  if (value == null || !isFinite(Number(value))) return <span className="text-textMuted">—</span>;
  const n = Number(value);
  const tone = n > 0 ? "text-success" : n < 0 ? "text-danger" : "text-textMuted";
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  return (
    <span className={`num ${tone} ${className}`}>
      {sign}
      {Math.abs(n).toFixed(digits).replace(".", ",")}
      {suffix}
    </span>
  );
}
