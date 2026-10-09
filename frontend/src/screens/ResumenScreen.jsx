import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getKpis, getHoldings, getUpcomingEvents } from "../api/portfolio";
import { listSnapshots } from "../api/snapshots";
import { useReconstructHistory } from "../hooks/useReconstructHistory";
import Card from "../components/Card.jsx";
import Delta from "../components/Delta.jsx";
import KpiCard from "../components/KpiCard.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import EmptyState from "../components/EmptyState.jsx";
import PageHeader from "../components/PageHeader.jsx";
import PortfolioLineChart from "../components/charts/PortfolioLineChart.jsx";
import AssetDonutChart from "../components/charts/AssetDonutChart.jsx";
import { formatARS, formatUSD } from "../utils/format";
import { useUiStore } from "../store/uiStore";
import { periodToDays } from "../utils/periods";

function efectiveVar(h) {
  const v = h.variacion_dia;
  if (v != null && Number(v) !== 0) return { value: Number(v), isYesterday: false };
  if (h.variacion_dia_prev != null) return { value: Number(h.variacion_dia_prev), isYesterday: true };
  return null;
}

function HoldingRow({ h, currency, fmt, showDesc = false }) {
  const val = currency === "USD" ? h.valuacion_usd : h.valuacion_ars;
  const ev = efectiveVar(h);
  return (
    <li className="flex items-center justify-between gap-3 py-2.5">
      <div className="min-w-0">
        <div className="text-sm font-medium text-text truncate">{h.simbolo}</div>
        <div className="text-xs text-textMuted truncate">
          {h.clase}
          {showDesc && h.descripcion ? ` · ${h.descripcion}` : ""}
        </div>
      </div>
      <div className="text-right shrink-0">
        <div className="text-sm text-text num">{fmt(val)}</div>
        {ev && (
          <div className="text-xs">
            <Delta value={ev.value} />
            {ev.isYesterday && <span className="text-textMuted ml-1">ayer</span>}
          </div>
        )}
      </div>
    </li>
  );
}

function Movers({ items, currency, fmt, empty }) {
  if (!items.length) return <div className="text-sm text-textMuted py-2">{empty}</div>;
  return (
    <ul className="divide-hair -my-2.5">
      {items.map((h) => (
        <HoldingRow key={h.id} h={h} currency={currency} fmt={fmt} />
      ))}
    </ul>
  );
}

function UpcomingPayments({ events }) {
  if (!events?.length)
    return (
      <div className="text-sm text-textMuted">
        Sin pagos estimados próximos (se necesita historial de operaciones).
      </div>
    );

  return (
    <div className="overflow-x-auto -mx-5">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-border">
            <th className="px-5 h-9 text-left text-xs font-medium text-textMuted">Símbolo</th>
            <th className="px-5 h-9 text-left text-xs font-medium text-textMuted">Tipo</th>
            <th className="px-5 h-9 text-left text-xs font-medium text-textMuted">Fecha estimada</th>
            <th className="px-5 h-9 text-right text-xs font-medium text-textMuted">Monto estimado</th>
          </tr>
        </thead>
        <tbody>
          {events.map((e, i) => (
            <tr key={i} className="border-b border-border last:border-b-0">
              <td className="px-5 py-2.5">
                <div className="font-medium text-text">{e.simbolo}</div>
                <div className="text-xs text-textMuted truncate max-w-[180px]">{e.descripcion}</div>
              </td>
              <td className="px-5 py-2.5 text-textSecondary">
                {e.event_kind === "RENTA" ? "Renta" : "Amortización"}
              </td>
              <td className="px-5 py-2.5 num text-textSecondary">{e.estimated_date}</td>
              <td className="px-5 py-2.5 text-right">
                <div className="num text-text">
                  {Number(e.last_amount) === 0 ? (
                    <span className="text-textMuted">pendiente</span>
                  ) : e.currency_kind?.startsWith("USD") ? (
                    formatUSD(e.last_amount)
                  ) : (
                    formatARS(e.last_amount)
                  )}
                </div>
                <div className="text-xs text-textMuted">
                  {e.interval_days > 0 ? `cada ~${e.interval_days} días` : "vencimiento"}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="px-5 pt-3 text-xs text-textMuted">
        Fechas y montos estimados sobre la tenencia actual. Corroborar con IOL.
      </div>
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
  const rebuild = useReconstructHistory();
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
  const renta = currency === "USD" ? k.renta_usd : k.renta_ars;
  const amort = currency === "USD" ? k.amortizaciones_usd : k.amortizaciones_ars;
  const divs = currency === "USD" ? k.dividendos_usd : k.dividendos_ars;

  const allHoldings = holdings.data || [];

  const withDaily = allHoldings.filter((h) => efectiveVar(h) !== null);
  // Filtramos por signo: sin esto "Más bajaron" completaba la lista con activos que subieron
  const gainers = withDaily
    .filter((h) => efectiveVar(h).value > 0)
    .sort((a, b) => efectiveVar(b).value - efectiveVar(a).value)
    .slice(0, 8);
  const losers = withDaily
    .filter((h) => efectiveVar(h).value < 0)
    .sort((a, b) => efectiveVar(a).value - efectiveVar(b).value)
    .slice(0, 8);

  const allSorted = [...allHoldings].sort((a, b) => Number(b.valuacion_ars) - Number(a.valuacion_ars));
  const displayHoldings = selectedClass
    ? allSorted.filter((h) => h.clase === selectedClass)
    : allSorted.slice(0, 5);

  const rate = Number(k.dolar_rate).toLocaleString("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  return (
    <div>
      <PageHeader title="Inversiones" subtitle={`Cartera IOL · ${k.dolar_source} ${rate}`} />

      <div className="space-y-4">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="col-span-2 lg:row-span-2">
            <KpiCard
              hero
              label="Valor total"
              value={fmt(currency === "USD" ? k.total_usd : k.total_ars)}
              sub={`${allHoldings.length} tenencias`}
            />
          </div>
          <KpiCard
            label="P&L no realizada"
            value={`${pnlNoReal > 0 ? "+" : ""}${fmt(pnlNoReal)}`}
            tone={pnlNoReal >= 0 ? "positive" : "negative"}
            sub="Valuación − costo"
          />
          <KpiCard label={`Renta ${k.kpi_year}`} value={fmt(renta)} sub="Al MEP de cada pago" />
          <KpiCard label={`Amortizaciones ${k.kpi_year}`} value={fmt(amort)} sub="Al MEP de cada pago" />
          <KpiCard label={`Dividendos ${k.kpi_year}`} value={fmt(divs)} sub="Al MEP de cada pago" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-stretch">
          <div className="lg:col-span-2">
            <PortfolioLineChart
              data={snaps.data || []}
              selectedClass={selectedClass}
              period={snapPeriod}
              onPeriodChange={setSnapPeriod}
              className="h-full min-h-[22rem]"
              emptyAction={
                <>
                  <button className="btn-secondary" onClick={rebuild.run} disabled={rebuild.running}>
                    {rebuild.running ? "Reconstruyendo…" : "Reconstruir el último año"}
                  </button>
                  {rebuild.running && rebuild.step && <span>{rebuild.step}</span>}
                  {rebuild.error && <span className="text-danger">{rebuild.error}</span>}
                </>
              }
            />
          </div>
          <AssetDonutChart
            data={k.distribucion_por_clase || []}
            selectedClass={selectedClass}
            onSelect={setSelectedClass}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card title="Más subieron" subtitle="Variación del día">
            <Movers items={gainers} currency={currency} fmt={fmt} empty="Ninguna tenencia subió hoy." />
          </Card>
          <Card title="Más bajaron" subtitle="Variación del día">
            <Movers items={losers} currency={currency} fmt={fmt} empty="Ninguna tenencia bajó hoy." />
          </Card>
        </div>

        <Card
          title={selectedClass ? `Tenencias · ${selectedClass}` : "Principales tenencias"}
          subtitle={selectedClass ? `${displayHoldings.length} activos` : "Top 5 por valuación"}
          action={
            selectedClass && (
              <button onClick={() => setSelectedClass(null)} className="btn-ghost h-7 px-2 text-xs">
                Quitar filtro
              </button>
            )
          }
        >
          {displayHoldings.length === 0 ? (
            <div className="text-sm text-textMuted">
              {selectedClass ? (
                `Sin tenencias de clase "${selectedClass}".`
              ) : (
                <>
                  Sin tenencias. Conectá IOL desde{" "}
                  <Link to="/ajustes" className="text-text underline underline-offset-2">
                    Ajustes
                  </Link>
                  .
                </>
              )}
            </div>
          ) : (
            <ul className="divide-hair -my-2.5">
              {displayHoldings.map((h) => (
                <HoldingRow key={h.id} h={h} currency={currency} fmt={fmt} showDesc />
              ))}
            </ul>
          )}
        </Card>

        <Card title="Próximos pagos" subtitle="ONs y bonos">
          {upcoming.isLoading ? (
            <div className="text-sm text-textMuted">Calculando…</div>
          ) : (
            <UpcomingPayments events={upcoming.data} />
          )}
        </Card>
      </div>
    </div>
  );
}
