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
import PeriodFilter from "./PeriodFilter";

export default function PortfolioLineChart({ data, selectedClass, period, onPeriodChange, title, className }) {
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

  // Devuelve el valor del punto inmediatamente anterior (día anterior) al de la fecha dada.
  const prevValue = useMemo(() => {
    return (currentDate) => {
      const idx = series.findIndex((d) => d.date === currentDate);
      if (idx <= 0) return null;
      return series[idx - 1][dataKey];
    };
  }, [series, dataKey]);

  const renderTooltip = ({ active, payload, label }) => {
    if (!active || !payload || payload.length === 0) return null;
    const value = payload[0].value;
    const prev = prevValue(label);
    let variation = null;
    if (prev != null && isFinite(prev) && prev !== 0) {
      variation = ((value - prev) / Math.abs(prev)) * 100;
    }
    const up = variation != null && variation >= 0;
    return (
      <div
        style={{
          background: t.tooltipBg,
          border: `1px solid ${t.tooltipBorder}`,
          borderRadius: 8,
          color: t.text,
          fontSize: 12,
          padding: "8px 10px",
        }}
      >
        <div style={{ color: t.axis, marginBottom: 2 }}>{formatDateShort(label)}</div>
        <div style={{ fontWeight: 600 }}>{fmt(value)}</div>
        <div style={{ color: t.axis, fontSize: 11, marginTop: 4 }}>
          vs. día anterior:{" "}
          {variation == null ? (
            <span style={{ color: t.axis }}>—</span>
          ) : (
            <span style={{ color: up ? t.success : t.danger, fontWeight: 600 }}>
              {up ? "+" : ""}
              {variation.toFixed(2)}%
            </span>
          )}
        </div>
      </div>
    );
  };

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
    <div className={`card p-4 ${className || "h-80"}`}>
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="label">
            {title || "Evolución de cartera"}
            {selectedClass && (
              <span className="ml-2 normal-case font-normal text-accent">
                · {selectedClass}
              </span>
            )}
          </div>
          <div className="text-xs text-textMuted">{currency}</div>
        </div>
        {onPeriodChange && <PeriodFilter value={period} onChange={onPeriodChange} />}
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
          <Tooltip wrapperStyle={{ zIndex: 50 }} content={renderTooltip} />
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
