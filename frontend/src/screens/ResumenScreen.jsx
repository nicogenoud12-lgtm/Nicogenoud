import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getKpis, getHoldings } from "../api/portfolio";
import { listSnapshots } from "../api/snapshots";
import KpiCard from "../components/KpiCard.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import EmptyState from "../components/EmptyState.jsx";
import PortfolioLineChart from "../components/charts/PortfolioLineChart.jsx";
import AssetDonutChart from "../components/charts/AssetDonutChart.jsx";
import { formatARS, formatUSD } from "../utils/format";
import { useUiStore } from "../store/uiStore";
import { periodToDays } from "../utils/periods";

export default function ResumenScreen() {
  const currency = useUiStore((s) => s.currency);
  const fmt = currency === "USD" ? formatUSD : formatARS;
  const [snapPeriod, setSnapPeriod] = useState("3M");
  const snapDays = periodToDays(snapPeriod);
  const kpis = useQuery({ queryKey: ["kpis"], queryFn: getKpis });
  const snaps = useQuery({ queryKey: ["snapshots", snapDays], queryFn: () => listSnapshots(snapDays) });
  const holdings = useQuery({ queryKey: ["holdings"], queryFn: () => getHoldings(false) });

  if (kpis.isLoading || snaps.isLoading) return <LoadingSpinner />;

  if (kpis.isError) {
    return (
      <EmptyState
        title="No se pudo cargar la información"
        description={kpis.error?.response?.data?.detail || String(kpis.error)}
        action={
          <Link to="/ajustes" className="btn-primary">
            Ir a Ajustes
          </Link>
        }
      />
    );
  }

  const k = kpis.data;
  const totalValue = currency === "USD" ? k.total_usd : k.total_ars;
  const pnlReal = currency === "USD" ? k.pnl_realizada_2026_usd : k.pnl_realizada_2026_ars;
  const pnlNoReal = k.pnl_no_realizada_ars; // IOL devuelve esto en ARS
  const renta = currency === "USD" ? k.renta_2026_usd : k.renta_2026_ars;
  const divs = currency === "USD" ? k.dividendos_2026_usd : k.dividendos_2026_ars;

  const topHoldings = (holdings.data || [])
    .slice()
    .sort((a, b) => Number(b.valuacion_ars) - Number(a.valuacion_ars))
    .slice(0, 5);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="Valor total" value={fmt(totalValue)} sub={`MEP ${k.dolar_source}: ${Number(k.dolar_rate).toFixed(2)}`} />
        <KpiCard
          label="P&L realizada 2026"
          value={fmt(pnlReal)}
          tone={pnlReal >= 0 ? "positive" : "negative"}
        />
        <KpiCard
          label="P&L no realizada"
          value={formatARS(pnlNoReal)}
          tone={pnlNoReal >= 0 ? "positive" : "negative"}
          sub="(de IOL, en ARS)"
        />
        <KpiCard
          label="N° operaciones 2026"
          value={k.n_operaciones_2026}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="Renta ONs 2026" value={fmt(renta)} />
        <KpiCard label="Dividendos 2026" value={fmt(divs)} />
        <KpiCard label="Valor (ARS)" value={formatARS(k.total_ars)} />
        <KpiCard label="Valor (USD)" value={formatUSD(k.total_usd)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <PortfolioLineChart data={snaps.data || []} period={snapPeriod} onPeriodChange={setSnapPeriod} />
        </div>
        <AssetDonutChart data={k.distribucion_por_clase || []} />
      </div>

      <div className="card p-4">
        <div className="label mb-3">Top 5 tenencias</div>
        {topHoldings.length === 0 ? (
          <div className="text-sm text-textMuted">
            Sin tenencias todavía. Conectá IOL desde{" "}
            <Link to="/ajustes" className="text-accent hover:underline">
              Ajustes
            </Link>
            .
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {topHoldings.map((h) => (
              <li key={h.id} className="py-2 flex items-center justify-between">
                <div>
                  <div className="font-medium">{h.simbolo}</div>
                  <div className="text-xs text-textMuted">
                    {h.clase} · {h.descripcion}
                  </div>
                </div>
                <div className="text-right tabular-nums">
                  <div>{fmt(currency === "USD" ? h.valuacion_usd : h.valuacion_ars)}</div>
                  <div
                    className={`text-xs ${
                      Number(h.ganancia_porcentaje || 0) >= 0
                        ? "text-success"
                        : "text-danger"
                    }`}
                  >
                    {Number(h.ganancia_porcentaje || 0).toFixed(2)}%
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
