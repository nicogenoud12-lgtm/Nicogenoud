import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { useUiStore } from "../../store/uiStore";
import { formatARS, formatUSD } from "../../utils/format";
import { palette, useChartTokens } from "./chartTheme";

export default function AssetDonutChart({ data }) {
  const currency = useUiStore((s) => s.currency);
  const t = useChartTokens();
  const fmt = currency === "USD" ? formatUSD : formatARS;
  const valueKey = currency === "USD" ? "valor_usd" : "valor_ars";

  const series = (data || []).map((d, i) => ({
    name: d.clase,
    value: Number(d[valueKey] || 0),
    pct: Number(d.pct || 0),
    color: palette[i % palette.length],
  }));

  const total = series.reduce((a, b) => a + b.value, 0);

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
            >
              {series.map((s, i) => (
                <Cell key={i} fill={s.color} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: t.tooltipBg,
                border: `1px solid ${t.tooltipBorder}`,
                borderRadius: 8,
                color: t.text,
                fontSize: 12,
              }}
              formatter={(value, _name, item) => [
                `${fmt(value)} (${(item.payload.pct || 0).toFixed(1)}%)`,
                item.payload.name,
              ]}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none px-2">
          <div className="text-[10px] uppercase tracking-wide text-textMuted">
            Total
          </div>
          <div
            className="font-semibold tabular-nums leading-tight text-center"
            style={{ fontSize: "clamp(0.7rem, 3.6vw, 1rem)" }}
          >
            {fmt(total)}
          </div>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 justify-center">
        {series.map((s) => (
          <div key={s.name} className="chip">
            <span
              className="inline-block h-2 w-2 rounded-full mr-1.5"
              style={{ background: s.color }}
            />
            {s.name} · {s.pct.toFixed(1)}%
          </div>
        ))}
      </div>
    </div>
  );
}
