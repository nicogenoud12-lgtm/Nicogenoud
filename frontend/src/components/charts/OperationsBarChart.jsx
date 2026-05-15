import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useUiStore } from "../../store/uiStore";
import { formatARS, formatUSD } from "../../utils/format";
import { useChartTokens } from "./chartTheme";

/**
 * data: [{ simbolo, pnl_ars, pnl_usd }]
 */
export default function OperationsBarChart({ data, title = "Resultado por símbolo" }) {
  const currency = useUiStore((s) => s.currency);
  const t = useChartTokens();
  const fmt = currency === "USD" ? formatUSD : formatARS;
  const key = currency === "USD" ? "pnl_usd" : "pnl_ars";

  const series = (data || [])
    .map((d) => ({ ...d, pnl: Number(d[key] || 0) }))
    .filter((d) => d.pnl !== 0)
    .sort((a, b) => Math.abs(b.pnl) - Math.abs(a.pnl))
    .slice(0, 10);

  const compactFmt = (v) => {
    const sign = v < 0 ? "-" : "";
    const abs = Math.abs(v);
    if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(1)}M`;
    if (abs >= 1_000) return `${sign}${Math.round(abs / 1_000)}k`;
    return `${sign}${Math.round(abs)}`;
  };

  return (
    <div className="card p-4 h-80">
      <div className="label mb-2">{title}</div>
      <ResponsiveContainer width="100%" height="85%">
        <BarChart
          data={series}
          layout="vertical"
          margin={{ top: 8, right: 12, left: 4, bottom: 8 }}
        >
          <CartesianGrid stroke={t.grid} strokeDasharray="3 3" horizontal={false} />
          <XAxis
            type="number"
            tickFormatter={compactFmt}
            tick={{ fill: t.axis, fontSize: 10 }}
            stroke={t.grid}
            tickCount={4}
          />
          <YAxis
            type="category"
            dataKey="simbolo"
            width={56}
            tick={{ fill: t.axis, fontSize: 11 }}
            stroke={t.grid}
          />
          <Tooltip
            cursor={{ fill: "transparent" }}
            wrapperStyle={{ zIndex: 50 }}
            contentStyle={{
              background: t.tooltipBg,
              border: `1px solid ${t.tooltipBorder}`,
              borderRadius: 8,
              color: t.text,
              fontSize: 12,
            }}
            formatter={(v) => [fmt(v), "Resultado"]}
          />
          <Bar dataKey="pnl" name="Resultado" radius={[0, 4, 4, 0]}>
            {series.map((s, i) => (
              <Cell key={i} fill={s.pnl >= 0 ? t.success : t.danger} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
