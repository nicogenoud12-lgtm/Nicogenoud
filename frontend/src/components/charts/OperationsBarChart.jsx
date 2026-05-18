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
import PeriodFilter from "./PeriodFilter";

export default function OperationsBarChart({ data, title = "Resultado por símbolo", period, onPeriodChange }) {
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
    <div className="card p-4 h-80">
      <div className="flex items-center justify-between mb-2">
        <div className="label">{title}</div>
        {onPeriodChange && <PeriodFilter value={period} onChange={onPeriodChange} />}
      </div>
      <ResponsiveContainer width="100%" height="85%">
        <BarChart
          data={series}
          layout="vertical"
          margin={{ top: 8, right: 16, left: 16, bottom: 8 }}
        >
          <CartesianGrid stroke={t.grid} strokeDasharray="3 3" horizontal={false} />
          <XAxis
            type="number"
            tickFormatter={(v) => fmt(v).replace(/\s/g, "")}
            tick={{ fill: t.axis, fontSize: 11 }}
            stroke={t.grid}
          />
          <YAxis
            type="category"
            dataKey="simbolo"
            width={80}
            tick={{ fill: t.axis, fontSize: 11 }}
            stroke={t.grid}
          />
          <Tooltip
            contentStyle={{
              background: t.tooltipBg,
              border: `1px solid ${t.tooltipBorder}`,
              borderRadius: 8,
              color: t.text,
            }}
            formatter={(v) => fmt(v)}
          />
          <Bar dataKey="pnl" radius={[0, 4, 4, 0]}>
            {series.map((s, i) => (
              <Cell key={i} fill={s.pnl >= 0 ? t.success : t.danger} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
