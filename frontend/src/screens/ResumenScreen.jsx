import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
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
  const [selectedClass, setSelectedClass] = useState(null);
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
  const pnlNoReal = currency === "USD" ? k.pnl_no_realizada_usd : k.pnl_no_realizada_ars;
  const renta = currency === "USD" ? k.renta_2026_usd : k.renta_2026_ars;
  const divs = currency === "USD" ? k.dividendos_2026_usd : k.dividendos_2026_ars;

  const allSorted = (holdings.data || [])
    .slice()
    .sort((a, b) => Number(b.valuacion_ars) - Number(a.valuacion_ars));

  const displayHoldings = selectedClass
    ? allSorted.filter((h) => h.clase === selectedClass)
    : allSorted.slice(0, 5);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard
          label="Valor total"
          value={fmt(totalValue)}
          sub={`MEP ${k.dolar_source}: ${Number(k.dolar_rate).toFixed(2)}`}
        />
        <KpiCard
          label="P&L no realizada"
          value={fmt(pnlNoReal)}
          tone={pnlNoReal >= 0 ? "positive" : "negative"}
          sub="de IOL (valuación actual − costo)"
        />
        <KpiCard label="N° operaciones 2026" value={k.n_operaciones_2026} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="Renta 2026" value={fmt(renta)} sub="convertido a MEP del día" />
        <KpiCard label="Dividendos 2026" value={fmt(divs)} sub="convertido a MEP del día" />
        <KpiCard label="Valor (ARS)" value={formatARS(k.total_ars)} />
        <KpiCard label="Valor (USD)" value={formatUSD(k.total_usd)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <PortfolioLineChart
            data={snaps.data || []}
            selectedClass={selectedClass}
            period={snapPeriod}
            onPeriodChange={setSnapPeriod}
          />
        </div>
        <AssetDonutChart
          data={k.distribucion_por_clase || []}
          selectedClass={selectedClass}
          onSelect={setSelectedClass}
        />
      </div>

      <div className="card p-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="label">
            {selectedClass ? `Tenencias · ${selectedClass}` : "Top 5 tenencias"}
          </div>
          {selectedClass && (
            <button
              onClick={() => setSelectedClass(null)}
              className="ml-auto text-xs chip cursor-pointer hover:bg-danger/20 hover:border-danger/40 hover:text-danger transition-colors"
            >
              ✕ Limpiar filtro
            </button>
          )}
        </div>

        {displayHoldings.length === 0 ? (
          <div className="text-sm text-textMuted">
            {selectedClass
              ? `Sin tenencias de clase "${selectedClass}".`
              : (
                <>
                  Sin tenencias todavía. Conectá IOL desde{" "}
                  <Link to="/ajustes" className="text-accent hover:underline">
                    Ajustes
                  </Link>
                  .
                </>
              )}
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {displayHoldings.map((h) => (
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
                      Number(h.ganancia_porcentaje || 0) >= 0 ? "text-success" : "text-danger"
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
