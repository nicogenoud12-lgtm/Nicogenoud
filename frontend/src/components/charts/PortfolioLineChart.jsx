import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useMemo } from "react";
import { useUiStore } from "../../store/uiStore";
import { formatARS, formatDateShort, formatUSD } from "../../utils/format";
import { useChartTokens } from "./chartTheme";

export default function PortfolioLineChart({ data, selectedClass }) {
  const currency = useUiStore((s) => s.currency);
  const t = useChartTokens();
  const dataKey = currency === "USD" ? "total_usd" : "total_ars";
  const fmt = currency === "USD" ? formatUSD : formatARS;

  const series = useMemo(() => {
    return (data || []).map((d) => {
      if (selectedClass && Array.isArray(d.breakdown_json) && d.breakdown_json.length > 0) {
        const filtered = d.breakdown_json.filter((h) => h.clase === selectedClass);
        return {
          ...d,
          total_ars: filtered.reduce((s, h) => s + Number(h.valuacion_ars || 0), 0),
          total_usd: filtered.reduce((s, h) => s + Number(h.valuacion_usd || 0), 0),
        };
      }
      return {
        ...d,
        total_ars: Number(d.total_ars || 0),
        total_usd: Number(d.total_usd || 0),
      };
    });
  }, [data, selectedClass]);

  const compactFmt = (v) => {
    const sign = v < 0 ? "-" : "";
    const abs = Math.abs(v);
    if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(1)}M`;
    if (abs >= 1_000) return `${sign}${Math.round(abs / 1_000)}k`;
    return `${sign}${Math.round(abs)}`;
  };

  const yDomain = useMemo(() => {
    const vals = series.map((d) => d[dataKey]).filter((v) => v != null && isFinite(v));
    if (vals.length === 0) return [0, "auto"];
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const pad = currency === "USD" ? 150 : 200_000;
    return [min - pad, max + pad];
  }, [series, dataKey, currency]);

  return (
    <div className="card p-4 h-80">
      <div className="flex items-baseline justify-between mb-2">
        <div>
          <div className="label">
            Evolución de cartera
            {selectedClass && (
              <span className="ml-2 normal-case font-normal text-accent">
                · {selectedClass}
              </span>
            )}
          </div>
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
            domain={yDomain}
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
