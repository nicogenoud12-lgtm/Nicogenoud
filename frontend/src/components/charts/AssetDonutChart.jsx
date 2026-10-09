import { useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { useUiStore } from "../../store/uiStore";
import { formatARS, formatUSD } from "../../utils/format";
import { colorFor, useChartTokens } from "./chartTheme";

const MAX_SLICES = 7; // el resto se agrupa en "Otros" (nunca se generan colores nuevos)

// `assets` (opcional): tenencias con simbolo/clase/valuacion_*. Con la clase elegida se
// despliegan sus activos y se puede elegir uno (`onSelectSymbol`).
export default function AssetDonutChart({
  data,
  selectedClass,
  onSelect,
  title,
  subtitle,
  assets,
  selectedSymbol,
  onSelectSymbol,
}) {
  const currency = useUiStore((s) => s.currency);
  const t = useChartTokens();
  const fmt = currency === "USD" ? formatUSD : formatARS;
  const valueKey = currency === "USD" ? "valor_usd" : "valor_ars";
  const [hoverIdx, setHoverIdx] = useState(null);

  const raw = (data || [])
    .map((d) => ({ name: d.clase, value: Number(d[valueKey] || 0), pct: Number(d.pct || 0) }))
    .filter((d) => d.value > 0)
    .sort((a, b) => b.value - a.value);
  const names = raw.map((r) => r.name);
  let series = raw.slice(0, MAX_SLICES).map((s) => ({ ...s, color: colorFor(s.name, names, t.categorical) }));
  const rest = raw.slice(MAX_SLICES);
  if (rest.length) {
    series.push({
      name: "Otros",
      value: rest.reduce((a, b) => a + b.value, 0),
      pct: rest.reduce((a, b) => a + b.pct, 0),
      other: true,
    });
  }
  series = series.map((s) => ({ ...s, color: s.color || t.axis }));

  const total = series.reduce((a, b) => a + b.value, 0);
  const assetValueKey = currency === "USD" ? "valuacion_usd" : "valuacion_ars";
  const classAssets =
    selectedClass && onSelectSymbol
      ? (assets || [])
          .filter((a) => a.clase === selectedClass && Number(a[assetValueKey]) > 0)
          .map((a) => ({ name: a.simbolo, value: Number(a[assetValueKey]) }))
          .sort((a, b) => b.value - a.value)
      : [];
  const selectedAsset = classAssets.find((a) => a.name === selectedSymbol);
  const selectedIdx = selectedClass != null ? series.findIndex((s) => s.name === selectedClass) : -1;
  const focus = hoverIdx ?? (selectedIdx >= 0 ? selectedIdx : null);
  const displaySeg =
    focus != null && hoverIdx != null
      ? series[focus]
      : selectedAsset
        ? { ...selectedAsset, pct: total ? (selectedAsset.value / total) * 100 : 0 }
        : focus != null
          ? series[focus]
          : null;
  const hasFilter = selectedClass != null;
  const canSelect = (s) => onSelect && !s.other;

  function toggle(s) {
    if (!canSelect(s)) return;
    onSelect(s.name === selectedClass ? null : s.name);
  }

  return (
    <section className="card card-pad flex flex-col">
      <div className="mb-2">
        <h2 className="section-title">{title || "Distribución por clase"}</h2>
        <div className="text-xs text-textMuted mt-0.5">
          {subtitle ||
            (onSelect
              ? onSelectSymbol
                ? "Tocá una clase para filtrar y elegí un activo"
                : "Tocá una clase para filtrar"
              : currency)}
        </div>
      </div>

      {series.length === 0 ? (
        <div className="h-48 grid place-items-center text-sm text-textMuted">Sin datos.</div>
      ) : (
        <>
          <div className="relative h-52">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={series}
                  dataKey="value"
                  nameKey="name"
                  innerRadius="70%"
                  outerRadius="94%"
                  stroke={t.surface}
                  strokeWidth={2}
                  startAngle={90}
                  endAngle={-270}
                  isAnimationActive={false}
                  onMouseEnter={(_, idx) => setHoverIdx(idx)}
                  onMouseLeave={() => setHoverIdx(null)}
                  onClick={(_, idx) => toggle(series[idx])}
                  style={{ cursor: onSelect ? "pointer" : "default" }}
                >
                  {series.map((s, i) => (
                    <Cell
                      key={s.name}
                      fill={s.color}
                      fillOpacity={
                        (hasFilter && s.name !== selectedClass && hoverIdx == null) ||
                        (hoverIdx != null && hoverIdx !== i)
                          ? 0.3
                          : 1
                      }
                    />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <div className="text-xs text-textMuted">{displaySeg ? displaySeg.name : "Total"}</div>
              <div className="text-base font-semibold tracking-tight mt-0.5 num">
                {fmt(displaySeg ? displaySeg.value : total)}
              </div>
              {displaySeg && (
                <div className="text-xs text-textMuted num">{displaySeg.pct.toFixed(1).replace(".", ",")}%</div>
              )}
            </div>
          </div>

          <ul className="mt-4 divide-hair">
            {series.map((s, i) => {
              const dim = hasFilter && s.name !== selectedClass;
              return (
                <li key={s.name}>
                  <button
                    type="button"
                    onClick={() => toggle(s)}
                    onMouseEnter={() => setHoverIdx(i)}
                    onMouseLeave={() => setHoverIdx(null)}
                    aria-pressed={s.name === selectedClass}
                    disabled={!canSelect(s)}
                    className={`w-full flex items-center gap-2.5 py-2 text-[13px] text-left transition-opacity disabled:cursor-default ${
                      dim ? "opacity-40" : ""
                    }`}
                  >
                    <span className="h-2 w-2 rounded-full shrink-0" style={{ background: s.color }} />
                    <span className="text-text flex-1 truncate">{s.name}</span>
                    <span className="text-textMuted num w-14 text-right">
                      {s.pct.toFixed(1).replace(".", ",")}%
                    </span>
                    <span className="text-text num w-32 text-right truncate">{fmt(s.value)}</span>
                  </button>
                  {s.name === selectedClass && classAssets.length > 0 && (
                    <ul className="pb-2">
                      {classAssets.map((a) => {
                        const active = a.name === selectedSymbol;
                        return (
                          <li key={a.name}>
                            <button
                              type="button"
                              onClick={() => onSelectSymbol(active ? null : a.name)}
                              aria-pressed={active}
                              className={`w-full flex items-center gap-2.5 py-1 pl-[18px] text-xs text-left rounded transition-colors ${
                                active ? "text-text font-medium" : "text-textSecondary hover:text-text"
                              } ${selectedSymbol && !active ? "opacity-50" : ""}`}
                            >
                              <span
                                className="h-1.5 w-1.5 rounded-full shrink-0 border"
                                style={{ borderColor: s.color, background: active ? s.color : "transparent" }}
                              />
                              <span className="flex-1 truncate">{a.name}</span>
                              <span className="text-textMuted num w-14 text-right">
                                {(total ? (a.value / total) * 100 : 0).toFixed(1).replace(".", ",")}%
                              </span>
                              <span className="num w-32 text-right truncate">{fmt(a.value)}</span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}
