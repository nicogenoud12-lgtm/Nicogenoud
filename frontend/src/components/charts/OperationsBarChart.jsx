import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useUiStore } from "../../store/uiStore";
import { formatARS, formatUSD } from "../../utils/format";
import { compactNumber, tooltipStyle, useChartTokens } from "./chartTheme";
import PeriodFilter from "./PeriodFilter";

// Una sola serie (el acento): el color no codifica nada más que "monto".
export default function OperationsBarChart({
  data,
  title = "Resultado por símbolo",
  subtitle,
  valueLabel = "Resultado",
  period,
  onPeriodChange,
}) {
  const currency = useUiStore((s) => s.currency);
  const t = useChartTokens();
  const fmt = currency === "USD" ? formatUSD : formatARS;
  const key = currency === "USD" ? "pnl_usd" : "pnl_ars";

  const series = (data || [])
    .map((d) => ({ ...d, pnl: Number(d[key] || 0) }))
    .filter((d) => d.pnl !== 0)
    .sort((a, b) => Math.abs(b.pnl) - Math.abs(a.pnl))
    .slice(0, 10);

  return (
    <section className="card card-pad flex flex-col h-[22rem]">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div className="min-w-0">
          <h2 className="section-title">{title}</h2>
          <div className="text-xs text-textMuted mt-0.5">{subtitle || `Top 10 · ${currency}`}</div>
        </div>
        {onPeriodChange && <PeriodFilter value={period} onChange={onPeriodChange} />}
      </div>
      <div className="flex-1 min-h-0">
        {series.length === 0 ? (
          <div className="h-full grid place-items-center text-sm text-textMuted">Sin cobros en el período.</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={series} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={t.grid} horizontal={false} />
              <XAxis
                type="number"
                tickFormatter={compactNumber}
                tick={{ fill: t.axis, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                tickCount={4}
              />
              <YAxis
                type="category"
                dataKey="simbolo"
                width={96}
                tickFormatter={(v) => String(v).replace(/ (US\$|USD|U\$S)$/, "")}
                tick={{ fill: t.textSecondary, fontSize: 12 }}
                axisLine={{ stroke: t.baseline }}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: t.grid, opacity: 0.6 }}
                wrapperStyle={{ zIndex: 50, outline: "none" }}
                contentStyle={tooltipStyle(t)}
                labelStyle={{ color: t.axis, marginBottom: 4 }}
                itemStyle={{ color: t.text, fontVariantNumeric: "tabular-nums" }}
                formatter={(v) => [fmt(v), valueLabel]}
              />
              <Bar
                dataKey="pnl"
                name={valueLabel}
                fill={t.accent}
                barSize={14}
                radius={[0, 4, 4, 0]}
                isAnimationActive={false}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}
