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

export default function AssetDonutChart({ data }) {
  const currency = useUiStore((s) => s.currency);
  const fmt = currency === "USD" ? formatUSD : formatARS;
  const valueKey = currency === "USD" ? "valor_usd" : "valor_ars";
  const [activeIdx, setActiveIdx] = useState(null);

  const series = (data || []).map((d, i) => ({
    name: d.clase,
    value: Number(d[valueKey] || 0),
    pct: Number(d.pct || 0),
    color: palette[i % palette.length],
  }));

  const total = series.reduce((a, b) => a + b.value, 0);
  const active = activeIdx != null ? series[activeIdx] : null;

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
              onMouseEnter={(_, idx) => setActiveIdx(idx)}
              onMouseLeave={() => setActiveIdx(null)}
            >
              {series.map((s, i) => (
                <Cell key={i} fill={s.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>

        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none px-3">
          {active ? (
            <>
              <div
                className="text-xs font-medium mb-0.5"
                style={{ color: active.color }}
              >
                {active.name}
              </div>
              <div
                className="font-semibold tabular-nums leading-tight text-center"
                style={{ fontSize: "clamp(0.65rem, 3.2vw, 0.95rem)" }}
              >
                {fmt(active.value)}
              </div>
              <div className="text-[11px] text-textMuted mt-0.5">
                {active.pct.toFixed(1)}%
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
            className={`chip transition-opacity ${
              activeIdx != null && activeIdx !== i ? "opacity-40" : ""
            }`}
            onMouseEnter={() => setActiveIdx(i)}
            onMouseLeave={() => setActiveIdx(null)}
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
