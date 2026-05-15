import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { getHoldings, getKpis } from "../api/portfolio";
import { operationsSummary } from "../api/operations";
import { listSnapshots } from "../api/snapshots";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import AssetDonutChart from "../components/charts/AssetDonutChart.jsx";
import OperationsBarChart from "../components/charts/OperationsBarChart.jsx";
import PortfolioLineChart from "../components/charts/PortfolioLineChart.jsx";
import { formatARS, formatPct, formatUSD } from "../utils/format";
import { useUiStore } from "../store/uiStore";

export default function AnalisisScreen() {
  const currency = useUiStore((s) => s.currency);
  const fmt = currency === "USD" ? formatUSD : formatARS;
  const kpis = useQuery({ queryKey: ["kpis"], queryFn: getKpis });
  const holdings = useQuery({ queryKey: ["holdings"], queryFn: () => getHoldings(false) });
  const snaps = useQuery({ queryKey: ["snapshots", 3650], queryFn: () => listSnapshots(3650) });
  const sum = useQuery({ queryKey: ["opsSummary", 2026], queryFn: () => operationsSummary(2026) });

  const performers = useMemo(() => {
    const list = (holdings.data || []).slice();
    list.sort((a, b) => Number(b.ganancia_porcentaje || 0) - Number(a.ganancia_porcentaje || 0));
    return { top: list.slice(0, 5), worst: list.slice(-5).reverse() };
  }, [holdings.data]);

  const opsByBucket = useMemo(() => {
    const bySim = (sum.data?.by_simbolo || []).map((s) => ({
      simbolo: s.simbolo,
      pnl_ars: Number(s.ventas_ars || 0) - Number(s.compras_ars || 0),
      pnl_usd: Number(s.ventas_usd || 0) - Number(s.compras_usd || 0),
    }));
    return bySim;
  }, [sum.data]);

  if (kpis.isLoading || holdings.isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Análisis</h1>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <AssetDonutChart data={kpis.data?.distribucion_por_clase || []} />
        <OperationsBarChart
          data={opsByBucket}
          title="Resultado neto por símbolo (Ventas − Compras)"
        />
      </div>
      <PortfolioLineChart data={snaps.data || []} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-4">
          <div className="label mb-3">Top performers</div>
          <ul className="divide-y divide-border">
            {performers.top.map((h) => (
              <li key={h.id} className="py-2 flex justify-between">
                <div>
                  <div className="font-medium">{h.simbolo}</div>
                  <div className="text-xs text-textMuted">{h.clase}</div>
                </div>
                <div className="text-right tabular-nums">
                  <div>{fmt(currency === "USD" ? h.valuacion_usd : h.valuacion_ars)}</div>
                  <div className="text-xs text-success">
                    {formatPct(h.ganancia_porcentaje)}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="card p-4">
          <div className="label mb-3">Worst performers</div>
          <ul className="divide-y divide-border">
            {performers.worst.map((h) => (
              <li key={h.id} className="py-2 flex justify-between">
                <div>
                  <div className="font-medium">{h.simbolo}</div>
                  <div className="text-xs text-textMuted">{h.clase}</div>
                </div>
                <div className="text-right tabular-nums">
                  <div>{fmt(currency === "USD" ? h.valuacion_usd : h.valuacion_ars)}</div>
                  <div className="text-xs text-danger">
                    {formatPct(h.ganancia_porcentaje)}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
