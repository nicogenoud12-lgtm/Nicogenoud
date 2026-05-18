import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getKpis, getHoldings, getUpcomingEvents } from "../api/portfolio";
import { listSnapshots } from "../api/snapshots";
import KpiCard from "../components/KpiCard.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import EmptyState from "../components/EmptyState.jsx";
import PortfolioLineChart from "../components/charts/PortfolioLineChart.jsx";
import AssetDonutChart from "../components/charts/AssetDonutChart.jsx";
import { formatARS, formatUSD, formatDate } from "../utils/format";
import { useUiStore } from "../store/uiStore";
import { periodToDays } from "../utils/periods";

function MoversTable({ items, currency, fmt, emptyMsg }) {
  if (!items.length) return <div className="text-sm text-textMuted py-2">{emptyMsg}</div>;
  return (
    <ul className="divide-y divide-border">
      {items.map((h) => {
        const val = currency === "USD" ? h.valuacion_usd : h.valuacion_ars;
        const pct = h.variacion_dia ?? h.ganancia_porcentaje ?? 0;
        const isPos = pct >= 0;
        return (
          <li key={h.id} className="py-2 flex items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="font-medium truncate">{h.simbolo}</div>
              <div className="text-xs text-textMuted truncate">{h.clase}</div>
            </div>
            <div className="text-right tabular-nums shrink-0">
              <div className="text-sm">{fmt(val)}</div>
              <div className={`text-xs font-semibold ${isPos ? "text-success" : "text-danger"}`}>
                {isPos ? "+" : ""}{Number(pct).toFixed(2)}%
                {h.variacion_dia == null && (
                  <span className="ml-1 text-textMuted font-normal opacity-60" title="P&L desde costo (dato diario no disponible)">*</span>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function UpcomingPayments({ events, currency, fmt }) {
  if (!events?.length) return (
    <div className="text-sm text-textMuted">Sin pagos estimados próximos (se requiere historial de operaciones).</div>
  );

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-textMuted uppercase">
            <th className="text-left pb-2 pr-4">Símbolo</th>
            <th className="text-left pb-2 pr-4">Tipo</th>
            <th className="text-left pb-2 pr-4">Fecha estimada</th>
            <th className="text-right pb-2">Último monto</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {events.map((e, i) => (
            <tr key={i}>
              <td className="py-2 pr-4">
                <div className="font-medium">{e.simbolo}</div>
                <div className="text-xs text-textMuted truncate max-w-[140px]">{e.descripcion}</div>
              </td>
              <td className="py-2 pr-4">
                <span className={`chip text-xs ${e.event_kind === "RENTA" ? "border-accent/40 text-accent" : "border-warn/40 text-warn"}`}>
                  {e.event_kind}
                </span>
              </td>
              <td className="py-2 pr-4 tabular-nums text-sm">{e.estimated_date}</td>
              <td className="py-2 text-right tabular-nums">
                {e.currency_kind !== "ARS"
                  ? `USD ${Number(e.last_amount).toLocaleString("es-AR", { minimumFractionDigits: 2 })}`
                  : formatARS(e.last_amount)
                }
                <div className="text-xs text-textMuted">cada ~{e.interval_days}d</div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-2 text-xs text-textMuted">* Fechas estimadas basadas en el historial de pagos. Corroborar con IOL.</div>
    </div>
  );
}

export default function ResumenScreen() {
  const currency = useUiStore((s) => s.currency);
  const fmt = currency === "USD" ? formatUSD : formatARS;
  const [selectedClass, setSelectedClass] = useState(null);
  const [snapPeriod, setSnapPeriod] = useState("3M");
  const snapDays = periodToDays(snapPeriod);

  const kpis = useQuery({ queryKey: ["kpis"], queryFn: getKpis });
  const snaps = useQuery({ queryKey: ["snapshots", snapDays], queryFn: () => listSnapshots(snapDays) });
  const holdings = useQuery({ queryKey: ["holdings"], queryFn: () => getHoldings(false) });
  const upcoming = useQuery({ queryKey: ["upcoming-events"], queryFn: getUpcomingEvents, staleTime: 300_000 });

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
  const pnlNoReal = currency === "USD" ? k.pnl_no_realizada_usd : k.pnl_no_realizada_ars;
  const renta = currency === "USD" ? k.renta_2026_usd : k.renta_2026_ars;
  const divs = currency === "USD" ? k.dividendos_2026_usd : k.dividendos_2026_ars;

  const allHoldings = holdings.data || [];

  // Sorted by variacion_dia first, fallback to ganancia_porcentaje
  const sortKey = (h) => h.variacion_dia ?? h.ganancia_porcentaje ?? 0;
  const sortedHoldings = [...allHoldings].sort((a, b) => sortKey(b) - sortKey(a));
  const gainers = sortedHoldings.slice(0, 10);
  const losers = [...allHoldings].sort((a, b) => sortKey(a) - sortKey(b)).slice(0, 10);

  const allSorted = [...allHoldings].sort((a, b) => Number(b.valuacion_ars) - Number(a.valuacion_ars));
  const displayHoldings = selectedClass
    ? allSorted.filter((h) => h.clase === selectedClass)
    : allSorted.slice(0, 5);

  const hasDailyData = allHoldings.some((h) => h.variacion_dia != null);

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard
          label="Valor total"
          value={fmt(currency === "USD" ? k.total_usd : k.total_ars)}
          sub={`MEP ${k.dolar_source}: ${Number(k.dolar_rate).toFixed(2)}`}
        />
        <KpiCard
          label="P&L no realizada"
          value={fmt(pnlNoReal)}
          tone={pnlNoReal >= 0 ? "positive" : "negative"}
          sub="valuación actual − costo"
        />
        <KpiCard label="Renta 2026" value={fmt(renta)} sub="MEP del día" />
        <KpiCard label="Dividendos 2026" value={fmt(divs)} sub="MEP del día" />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-stretch">
        <div className="lg:col-span-2">
          <PortfolioLineChart
            data={snaps.data || []}
            selectedClass={selectedClass}
            period={snapPeriod}
            onPeriodChange={setSnapPeriod}
            className="card p-4 h-full min-h-[20rem]"
          />
        </div>
        <AssetDonutChart
          data={k.distribucion_por_clase || []}
          selectedClass={selectedClass}
          onSelect={setSelectedClass}
        />
      </div>

      {/* Movers */}
      {!hasDailyData && (
        <div className="text-xs text-textMuted">
          * Variación diaria no disponible desde IOL en este momento. Se muestra P&L desde costo como referencia.
        </div>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-4">
          <div className="label mb-3">Más subieron {hasDailyData ? "hoy" : "(P&L)"}</div>
          <MoversTable items={gainers} currency={currency} fmt={fmt} emptyMsg="Sin tenencias." />
        </div>
        <div className="card p-4">
          <div className="label mb-3">Más bajaron {hasDailyData ? "hoy" : "(P&L)"}</div>
          <MoversTable items={losers} currency={currency} fmt={fmt} emptyMsg="Sin tenencias." />
        </div>
      </div>

      {/* Top 5 tenencias */}
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
            {selectedClass ? `Sin tenencias de clase "${selectedClass}".` : (
              <>Sin tenencias. Conectá IOL desde <Link to="/ajustes" className="text-accent hover:underline">Ajustes</Link>.</>
            )}
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {displayHoldings.map((h) => (
              <li key={h.id} className="py-2 flex items-center justify-between">
                <div>
                  <div className="font-medium">{h.simbolo}</div>
                  <div className="text-xs text-textMuted">{h.clase} · {h.descripcion}</div>
                </div>
                <div className="text-right tabular-nums">
                  <div>{fmt(currency === "USD" ? h.valuacion_usd : h.valuacion_ars)}</div>
                  <div className={`text-xs ${Number(h.ganancia_porcentaje || 0) >= 0 ? "text-success" : "text-danger"}`}>
                    {Number(h.ganancia_porcentaje || 0).toFixed(2)}%
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Upcoming payments */}
      <div className="card p-4">
        <div className="label mb-3">Próximos pagos — ONs y Bonos</div>
        {upcoming.isLoading ? (
          <div className="text-sm text-textMuted">Calculando...</div>
        ) : (
          <UpcomingPayments events={upcoming.data} currency={currency} fmt={fmt} />
        )}
      </div>
    </div>
  );
}
