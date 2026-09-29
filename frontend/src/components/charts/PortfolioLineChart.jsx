import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useMemo } from "react";
import { useUiStore } from "../../store/uiStore";
import { formatARS, formatDateShort, formatUSD } from "../../utils/format";
import { timeWeightedReturns } from "../../utils/performance";
import { compactNumber, tooltipStyle, useChartTokens } from "./chartTheme";
import PeriodFilter from "./PeriodFilter";

// Decimales justos para un tick de %: 5% · 0,5% · 0,25%
const tickDecimals = (v) => {
  if (Math.abs(v - Math.round(v)) < 1e-9) return 0;
  if (Math.abs(v * 10 - Math.round(v * 10)) < 1e-9) return 1;
  return 2;
};

export default function PortfolioLineChart({ data, selectedClass, period, onPeriodChange, title, className }) {
  const currency = useUiStore((s) => s.currency);
  const evoMode = useUiStore((s) => s.evoMode);
  const setEvoMode = useUiStore((s) => s.setEvoMode);
  const isPerf = evoMode === "rendimiento";
  const t = useChartTokens();
  const dataKey = currency === "USD" ? "total_usd" : "total_ars";
  const fmt = currency === "USD" ? formatUSD : formatARS;

  const flowKey = currency === "USD" ? "usd" : "ars";

  const series = useMemo(() => {
    // Un total en 0 nunca es real (snapshot guardado cuando falló IOL): se descarta
    // para que no hunda la escala. En el filtro por clase el 0 sí es válido (no había de esa clase).
    const valid = (data || []).filter((d) => Number(d[dataKey]) > 0);
    const base = valid.map((d) => {
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
    const perf = timeWeightedReturns(base.map((d) => ({ value: d[dataKey], flow: d[`flujo_${flowKey}`] })));
    return base.map((d, i) => ({ ...d, ...perf[i] }));
  }, [data, selectedClass, dataKey, flowKey]);

  const byDate = useMemo(() => {
    const m = new Map();
    series.forEach((d, i) => m.set(d.date, i));
    return m;
  }, [series]);

  const pct = (v, digits = 2) => {
    const txt = Math.abs(v).toFixed(digits);
    if (Number(txt) === 0) return "0%";
    return `${v > 0 ? "+" : "−"}${txt.replace(".", ",")}%`;
  };
  const hasFlowMarks = series.some((d) => d.flowMark !== 0);

  const renderTooltip = ({ active, label }) => {
    if (!active || label == null) return null;
    const idx = byDate.get(label);
    if (idx == null) return null;
    const point = series[idx];
    const prevPoint = idx > 0 ? series[idx - 1] : null;
    const flujo = point[`flujo_${flowKey}`];
    const variation = point.dayPct;
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
    const tone = (v) => (v > 0 ? t.success : v < 0 ? t.danger : t.axis);
    const muted = { color: t.axis, fontSize: 11, marginTop: 3 };
    return (
      <div style={tooltipStyle(t)}>
        <div style={{ color: t.axis, marginBottom: 4 }}>{formatDateShort(label)}</div>
        {isPerf ? (
          <>
            <div style={{ fontWeight: 600, fontSize: 13, color: tone(point.cumPct), fontVariantNumeric: "tabular-nums" }}>
              {pct(point.cumPct)} <span style={{ color: t.axis, fontWeight: 400 }}>en el período</span>
            </div>
            <div style={muted}>Valor: {fmt(point[dataKey])}</div>
          </>
        ) : (
          <div style={{ fontWeight: 600, fontSize: 13, fontVariantNumeric: "tabular-nums" }}>{fmt(point[dataKey])}</div>
        )}
        <div style={muted}>
          vs. {vsLabel}:{" "}
          {variation == null ? (
            <span>—</span>
          ) : (
            <span style={{ color: tone(variation), fontWeight: 600 }}>{pct(variation)}</span>
          )}
        </div>
        {prevPoint && Math.abs(flujo) >= 0.01 && (
          <div style={muted}>
            {flujo > 0 ? "Compras netas" : "Ventas / amortizaciones"}: {fmt(Math.abs(flujo))}
          </div>
        )}
      </div>
    );
  };

  const valueKey = isPerf ? "cumPct" : dataKey;

  // Dominio y ticks del eje. En rendimiento los ticks se calculan a mano (pasos redondos que
  // siempre incluyen el 0), porque recharts descarta ticks intermedios con dominios no redondos.
  const { yDomain, yTicks } = useMemo(() => {
    const vals = series.map((d) => d[valueKey]).filter((v) => v != null && isFinite(v));
    if (vals.length === 0) return { yDomain: [0, "auto"], yTicks: undefined };
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    if (isPerf) {
      const lo = Math.min(0, min);
      const hi = Math.max(0, max);
      const span = Math.max(hi - lo, 0.5);
      const step = [0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10, 20, 25, 50, 100, 200, 500].find((s) => span / s <= 5) || 1000;
      const first = Math.floor(lo / step) * step - (lo <= Math.floor(lo / step) * step + step * 0.1 ? step : 0);
      const last = Math.ceil(hi / step) * step + (hi >= Math.ceil(hi / step) * step - step * 0.1 ? step : 0);
      const ticks = [];
      for (let v = first; v <= last + step / 2; v += step) ticks.push(Number(v.toFixed(6)));
      return { yDomain: [first, last], yTicks: ticks };
    }
    const pad = Math.max((max - min) * 0.15, max * 0.01);
    return { yDomain: [Math.max(0, min - pad), max + pad], yTicks: undefined };
  }, [series, valueKey, isPerf]);

  // Marca de compra (punto lleno) o venta/amortización (punto hueco) sobre la línea de valor
  const renderFlowDot = (props) => {
    const { cx, cy, payload, index } = props;
    if (isPerf || !payload?.flowMark || cx == null || cy == null) return <g key={`f-${index}`} />;
    const buy = payload.flowMark > 0;
    return (
      <circle
        key={`f-${index}`}
        cx={cx}
        cy={cy}
        r={4.5}
        fill={buy ? t.text : t.surface}
        stroke={buy ? t.surface : t.text}
        strokeWidth={2}
      />
    );
  };

  const gradientId = `evo-fill-${t.mode}`;

  return (
    <section className={`card card-pad flex flex-col ${className || "h-[22rem]"}`}>
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div className="min-w-0">
          <h2 className="section-title">
            {title || "Evolución de cartera"}
            {selectedClass && <span className="ml-1.5 font-normal text-textMuted">· {selectedClass}</span>}
          </h2>
          <div className="text-xs text-textMuted mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>{isPerf ? "Rendimiento sin compras ni ventas" : currency}</span>
            {!isPerf && hasFlowMarks && (
              <>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-text" aria-hidden />
                  Compra
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full border-[1.5px] border-text" aria-hidden />
                  Venta / amortización
                </span>
              </>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="segmented" role="group" aria-label="Vista del gráfico">
            {[
              ["valor", "Valor"],
              ["rendimiento", "Rendimiento"],
            ].map(([k, lbl]) => (
              <button
                key={k}
                onClick={() => setEvoMode(k)}
                aria-pressed={evoMode === k}
                className={`segmented-item h-6 ${evoMode === k ? "segmented-item-active" : ""}`}
              >
                {lbl}
              </button>
            ))}
          </div>
          {onPeriodChange && <PeriodFilter value={period} onChange={onPeriodChange} />}
        </div>
      </div>
      <div className="flex-1 min-h-0">
        {series.length === 0 ? (
          <div className="h-full grid place-items-center text-sm text-textMuted">Sin snapshots en el período.</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={series} margin={{ top: 6, right: 6, left: 0, bottom: 0 }}>
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
                tickFormatter={isPerf ? (v) => pct(v, tickDecimals(v)) : compactNumber}
                tick={{ fill: t.axis, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={48}
                domain={yDomain}
                ticks={yTicks}
                interval={isPerf ? 0 : "preserveEnd"}
              />
              {isPerf && <ReferenceLine y={0} stroke={t.baseline} />}
              <Tooltip
                wrapperStyle={{ zIndex: 50, outline: "none" }}
                content={renderTooltip}
                cursor={{ stroke: t.baseline, strokeWidth: 1 }}
              />
              <Area
                type="monotone"
                dataKey={valueKey}
                baseValue={isPerf ? 0 : undefined}
                stroke={t.accent}
                strokeWidth={2}
                fill={isPerf ? "none" : `url(#${gradientId})`}
                dot={renderFlowDot}
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
