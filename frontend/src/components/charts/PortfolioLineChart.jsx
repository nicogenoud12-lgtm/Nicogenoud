import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useUiStore } from "../../store/uiStore";
import { formatARS, formatDateShort, formatUSD } from "../../utils/format";
import { useChartTokens } from "./chartTheme";
import PeriodFilter from "./PeriodFilter";

export default function PortfolioLineChart({ data, period, onPeriodChange }) {
  const currency = useUiStore((s) => s.currency);
  const t = useChartTokens();
  const dataKey = currency === "USD" ? "total_usd" : "total_ars";
  const fmt = currency === "USD" ? formatUSD : formatARS;

  const series = (data || []).map((d) => ({
    ...d,
    total_ars: Number(d.total_ars || 0),
    total_usd: Number(d.total_usd || 0),
  }));

  return (
    <div className="card p-4 h-80">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="label">Evolución de cartera</div>
          <div className="text-xs text-textMuted">{currency}</div>
        </div>
        {onPeriodChange && <PeriodFilter value={period} onChange={onPeriodChange} />}
      </div>
      <ResponsiveContainer width="100%" height="85%">
        <LineChart data={series} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
          <CartesianGrid stroke={t.grid} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={formatDateShort}
            tick={{ fill: t.axis, fontSize: 11 }}
            stroke={t.grid}
          />
          <YAxis
            tickFormatter={(v) => fmt(v).replace(/\s/g, "")}
            tick={{ fill: t.axis, fontSize: 11 }}
            stroke={t.grid}
            width={90}
          />
          <Tooltip
            contentStyle={{
              background: t.tooltipBg,
              border: `1px solid ${t.tooltipBorder}`,
              borderRadius: 8,
              color: t.text,
            }}
            labelFormatter={formatDateShort}
            formatter={(value, name) => [fmt(value), name === "total_ars" ? "ARS" : "USD"]}
          />
          <Line
            type="monotone"
            dataKey={dataKey}
            stroke={t.accent}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
