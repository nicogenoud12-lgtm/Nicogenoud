import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useMemo } from "react";
import { useUiStore } from "../../store/uiStore";
import { formatARS, formatDateShort, formatUSD } from "../../utils/format";
import { compactNumber, tooltipStyle, useChartTokens } from "./chartTheme";
import PeriodFilter from "./PeriodFilter";

export default function PortfolioLineChart({ data, selectedClass, period, onPeriodChange, title, className }) {
  const currency = useUiStore((s) => s.currency);
  const t = useChartTokens();
  const dataKey = currency === "USD" ? "total_usd" : "total_ars";
  const fmt = currency === "USD" ? formatUSD : formatARS;

  const flowKey = currency === "USD" ? "usd" : "ars";

  const series = useMemo(() => {
    // Un total en 0 nunca es real (snapshot guardado cuando falló IOL): se descarta
    // para que no hunda la escala. En el filtro por clase el 0 sí es válido (no había de esa clase).
    const valid = (data || []).filter((d) => Number(d[dataKey]) > 0);
    return valid.map((d) => {
      // flujo = plata que entró (+) o salió (−) desde el punto anterior (compras, ventas, amortizaciones)
      if (selectedClass && Array.isArray(d.breakdown_json) && d.breakdown_json.length > 0) {
        const filtered = d.breakdown_json.filter((h) => h.clase === selectedClass);
        const f = d.flujo_por_clase?.[selectedClass] || {};
        return {
          ...d,
          total_ars: filtered.reduce((s, h) => s + Number(h.valuacion_ars || 0), 0),
          total_usd: filtered.reduce((s, h) => s + Number(h.valuacion_usd || 0), 0),
          flujo_ars: Number(f.ars || 0),
          flujo_usd: Number(f.usd || 0),
        };
      }
      return {
        ...d,
        total_ars: Number(d.total_ars || 0),
        total_usd: Number(d.total_usd || 0),
        flujo_ars: Number(d.flujo_ars || 0),
        flujo_usd: Number(d.flujo_usd || 0),
      };
    });
  }, [data, selectedClass, dataKey]);

  const byDate = useMemo(() => {
    const m = new Map();
    series.forEach((d, i) => m.set(d.date, i));
    return m;
  }, [series]);

  const renderTooltip = ({ active, payload, label }) => {
    if (!active || !payload || payload.length === 0) return null;
    const value = payload[0].value;
    const idx = byDate.get(label);
    const prevPoint = idx > 0 ? series[idx - 1] : null;
    const prev = prevPoint ? prevPoint[dataKey] : null;
    const flujo = idx != null ? series[idx][`flujo_${flowKey}`] : 0;
    // Variación de rendimiento: descuenta aportes/retiros para que una compra no parezca ganancia
    let variation = null;
    if (prev != null && isFinite(prev) && prev !== 0) {
      variation = ((value - prev - flujo) / Math.abs(prev)) * 100;
    }
    const up = variation != null && variation >= 0;
    // Si faltó algún snapshot, aclaramos contra qué fecha se compara
    let vsLabel = "día anterior";
    if (prevPoint) {
      const [y, m, d] = label.split("-").map(Number);
      const expected = new Date(y, m - 1, d - 1);
      const [py, pm, pd] = prevPoint.date.split("-").map(Number);
      if (expected.getTime() !== new Date(py, pm - 1, pd).getTime()) {
        vsLabel = formatDateShort(prevPoint.date);
      }
    }
    return (
      <div style={tooltipStyle(t)}>
        <div style={{ color: t.axis, marginBottom: 4 }}>{formatDateShort(label)}</div>
        <div style={{ fontWeight: 600, fontSize: 13, fontVariantNumeric: "tabular-nums" }}>{fmt(value)}</div>
        <div style={{ color: t.axis, fontSize: 11, marginTop: 4 }}>
          vs. {vsLabel}:{" "}
          {variation == null ? (
            <span style={{ color: t.axis }}>—</span>
          ) : (
            <span style={{ color: up ? t.success : t.danger, fontWeight: 600 }}>
              {up ? "+" : "−"}
              {Math.abs(variation).toFixed(2).replace(".", ",")}%
            </span>
          )}
        </div>
        {prevPoint && Math.abs(flujo) >= 0.01 && (
          <div style={{ color: t.axis, fontSize: 11, marginTop: 2 }}>
            {flujo > 0 ? "Aportes" : "Retiros"} netos: {fmt(Math.abs(flujo))}
          </div>
        )}
      </div>
    );
  };

  const yDomain = useMemo(() => {
    const vals = series.map((d) => d[dataKey]).filter((v) => v != null && isFinite(v));
    if (vals.length === 0) return [0, "auto"];
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const pad = Math.max((max - min) * 0.15, max * 0.01);
    return [Math.max(0, min - pad), max + pad];
  }, [series, dataKey]);

  const gradientId = `evo-fill-${t.mode}`;

  return (
    <section className={`card card-pad flex flex-col ${className || "h-[22rem]"}`}>
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div className="min-w-0">
          <h2 className="section-title">
            {title || "Evolución de cartera"}
            {selectedClass && <span className="ml-1.5 font-normal text-textMuted">· {selectedClass}</span>}
          </h2>
          <div className="text-xs text-textMuted mt-0.5">{currency}</div>
        </div>
        {onPeriodChange && <PeriodFilter value={period} onChange={onPeriodChange} />}
      </div>
      <div className="flex-1 min-h-0">
        {series.length === 0 ? (
          <div className="h-full grid place-items-center text-sm text-textMuted">Sin snapshots en el período.</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={series} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={t.accent} stopOpacity={0.14} />
                  <stop offset="100%" stopColor={t.accent} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={t.grid} vertical={false} />
              <XAxis
                dataKey="date"
                tickFormatter={formatDateShort}
                tick={{ fill: t.axis, fontSize: 11 }}
                axisLine={{ stroke: t.baseline }}
                tickLine={false}
                minTickGap={32}
                tickMargin={8}
              />
              <YAxis
                tickFormatter={compactNumber}
                tick={{ fill: t.axis, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={44}
                domain={yDomain}
              />
              <Tooltip
                wrapperStyle={{ zIndex: 50, outline: "none" }}
                content={renderTooltip}
                cursor={{ stroke: t.baseline, strokeWidth: 1 }}
              />
              <Area
                type="monotone"
                dataKey={dataKey}
                stroke={t.accent}
                strokeWidth={2}
                fill={`url(#${gradientId})`}
                dot={false}
                activeDot={{ r: 4, fill: t.accent, stroke: t.surface, strokeWidth: 2 }}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}
