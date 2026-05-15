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
    <div className="card p-4 h-80">
      <div className="label mb-2">Distribución por clase</div>
      <ResponsiveContainer width="100%" height="85%">
        <PieChart>
          <Pie
            data={series}
            dataKey="value"
            nameKey="name"
            innerRadius={60}
            outerRadius={100}
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
            }}
            formatter={(value, _name, item) => [
              `${fmt(value)} (${(item.payload.pct || 0).toFixed(1)}%)`,
              item.payload.name,
            ]}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="text-center -mt-44 pointer-events-none">
        <div className="text-xs text-textMuted">Total</div>
        <div className="text-lg font-semibold tabular-nums">{fmt(total)}</div>
      </div>
      <div className="mt-2 flex flex-wrap gap-2 justify-center">
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
