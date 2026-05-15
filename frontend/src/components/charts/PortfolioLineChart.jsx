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

export default function PortfolioLineChart({ data }) {
  const currency = useUiStore((s) => s.currency);
  const t = useChartTokens();
  const dataKey = currency === "USD" ? "total_usd" : "total_ars";
  const fmt = currency === "USD" ? formatUSD : formatARS;

  const series = (data || []).map((d) => ({
    ...d,
    total_ars: Number(d.total_ars || 0),
    total_usd: Number(d.total_usd || 0),
  }));

  const compactFmt = (v) => {
    const sign = v < 0 ? "-" : "";
    const abs = Math.abs(v);
    if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(1)}M`;
    if (abs >= 1_000) return `${sign}${Math.round(abs / 1_000)}k`;
    return `${sign}${Math.round(abs)}`;
  };

  return (
    <div className="card p-4 h-80">
      <div className="flex items-baseline justify-between mb-2">
        <div>
          <div className="label">Evolución de cartera</div>
          <div className="text-xs text-textMuted">{currency}</div>
        </div>
      </div>
      <ResponsiveContainer width="100%" height="85%">
        <LineChart data={series} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
          <CartesianGrid stroke={t.grid} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={formatDateShort}
            tick={{ fill: t.axis, fontSize: 10 }}
            stroke={t.grid}
            minTickGap={24}
          />
          <YAxis
            tickFormatter={compactFmt}
            tick={{ fill: t.axis, fontSize: 10 }}
            stroke={t.grid}
            width={44}
          />
          <Tooltip
            wrapperStyle={{ zIndex: 50 }}
            contentStyle={{
              background: t.tooltipBg,
              border: `1px solid ${t.tooltipBorder}`,
              borderRadius: 8,
              color: t.text,
              fontSize: 12,
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
