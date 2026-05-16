import { useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Sector } from "recharts";
import { useUiStore } from "../../store/uiStore";
import { formatARS, formatUSD } from "../../utils/format";
import { palette } from "./chartTheme";

function ActiveSlice(props) {
  const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill } = props;
  return (
    <Sector
      cx={cx}
      cy={cy}
      innerRadius={Number(innerRadius) - 4}
      outerRadius={Number(outerRadius) + 6}
      startAngle={startAngle}
      endAngle={endAngle}
      fill={fill}
    />
  );
}

export default function AssetDonutChart({ data, selectedClass, onSelect }) {
  const currency = useUiStore((s) => s.currency);
  const fmt = currency === "USD" ? formatUSD : formatARS;
  const valueKey = currency === "USD" ? "valor_usd" : "valor_ars";
  const [hoverIdx, setHoverIdx] = useState(null);

  const series = (data || [])
    .map((d) => ({
      name: d.clase,
      value: Number(d[valueKey] || 0),
      pct: Number(d.pct || 0),
    }))
    .sort((a, b) => b.value - a.value)
    .map((s, i) => ({ ...s, color: palette[i % palette.length] }));

  const total = series.reduce((a, b) => a + b.value, 0);

  const selectedIdx = selectedClass != null
    ? series.findIndex((s) => s.name === selectedClass)
    : null;

  // What to show in the center:
  // 1. Hovering → hovered segment
  // 2. Class selected → selected segment
  // 3. Nothing → Total
  const displaySeg =
    hoverIdx != null
      ? series[hoverIdx]
      : selectedIdx != null && selectedIdx >= 0
        ? series[selectedIdx]
        : null;

  const activeIdx = hoverIdx ?? (selectedIdx >= 0 ? selectedIdx : null);

  function handleClick(_, idx) {
    if (!onSelect) return;
    const name = series[idx]?.name;
    onSelect(name === selectedClass ? null : name);
  }

  const hasFilter = selectedClass != null;

  return (
    <div className="card p-4">
      <div className="label mb-2">Distribución por clase</div>
      <div className="relative h-64 sm:h-72">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={series}
              dataKey="value"
              nameKey="name"
              innerRadius="58%"
              outerRadius="88%"
              paddingAngle={2}
              stroke="none"
              activeIndex={activeIdx}
              activeShape={ActiveSlice}
              onMouseEnter={(_, idx) => setHoverIdx(idx)}
              onMouseLeave={() => setHoverIdx(null)}
              onClick={handleClick}
              style={{ cursor: onSelect ? "pointer" : "default" }}
            >
              {series.map((s, i) => (
                <Cell
                  key={i}
                  fill={s.color}
                  fillOpacity={
                    hasFilter && s.name !== selectedClass && hoverIdx == null
                      ? 0.25
                      : 1
                  }
                />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>

        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none px-3">
          {displaySeg ? (
            <>
              <div
                className="text-xs font-medium mb-0.5 text-center"
                style={{ color: displaySeg.color }}
              >
                {displaySeg.name}
              </div>
              <div
                className="font-semibold tabular-nums leading-tight text-center"
                style={{ fontSize: "clamp(0.65rem, 3.2vw, 0.95rem)" }}
              >
                {fmt(displaySeg.value)}
              </div>
              <div className="text-[11px] text-textMuted mt-0.5">
                {displaySeg.pct.toFixed(1)}%
              </div>
            </>
          ) : (
            <>
              <div className="text-[10px] uppercase tracking-wide text-textMuted">
                Total
              </div>
              <div
                className="font-semibold tabular-nums leading-tight text-center"
                style={{ fontSize: "clamp(0.7rem, 3.6vw, 1rem)" }}
              >
                {fmt(total)}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 justify-center">
        {series.map((s, i) => (
          <button
            key={s.name}
            type="button"
            onClick={() => onSelect && onSelect(s.name === selectedClass ? null : s.name)}
            className={`chip transition-opacity ${
              hasFilter && s.name !== selectedClass ? "opacity-30" : ""
            } ${onSelect ? "cursor-pointer hover:opacity-100" : ""}`}
            onMouseEnter={() => setHoverIdx(i)}
            onMouseLeave={() => setHoverIdx(null)}
          >
            <span
              className="inline-block h-2 w-2 rounded-full mr-1.5"
              style={{ background: s.color }}
            />
            {s.name} · {s.pct.toFixed(1)}%
          </button>
        ))}
      </div>
    </div>
  );
}
