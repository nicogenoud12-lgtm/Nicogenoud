import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  listOperations,
  operationsSummary,
  operationYears,
  syncHistory,
  syncHistoryStatus,
  syncOperations,
} from "../api/operations";
import { useBackgroundJob } from "../hooks/useBackgroundJob";
import DataTable from "../components/DataTable.jsx";
import KpiCard from "../components/KpiCard.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import PageHeader from "../components/PageHeader.jsx";
import { formatARS, formatDate, formatNumber, formatUSD } from "../utils/format";
import { useUiStore } from "../store/uiStore";

const KINDS = ["COMPRA", "VENTA", "SUSCRIPCION", "RESCATE", "RENTA", "AMORTIZACION", "DIVIDENDO"];
const KIND_LABEL = {
  COMPRA: "Compra",
  VENTA: "Venta",
  SUSCRIPCION: "Suscripción",
  RESCATE: "Rescate",
  RENTA: "Renta",
  AMORTIZACION: "Amortización",
  DIVIDENDO: "Dividendo",
  OTRO: "Otro",
};
const CURRENCY_LABEL = { ARS: "ARS", USD_MEP: "USD MEP", USD_CABLE: "USD Cable" };

export default function OperacionesScreen() {
  const currency = useUiStore((s) => s.currency);
  const qc = useQueryClient();
  const currentYear = new Date().getFullYear();
  const yearsQ = useQuery({ queryKey: ["opYears"], queryFn: operationYears });
  // Años con operaciones guardadas (incluye el actual aunque todavía no haya datos)
  const years = yearsQ.data?.length ? yearsQ.data : [currentYear];
  const [year, setYear] = useState(currentYear);
  const [kinds, setKinds] = useState([]);
  const [search, setSearch] = useState("");

  const ops = useQuery({
    queryKey: ["operations", year],
    queryFn: () => listOperations({ year }),
  });
  const sum = useQuery({
    queryKey: ["opsSummary", year],
    queryFn: () => operationsSummary({ fromDate: `${year}-01-01`, toDate: `${year}-12-31` }),
  });
  const sync = useMutation({
    mutationFn: () => syncOperations(year),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["operations", year] });
      qc.invalidateQueries({ queryKey: ["opsSummary", year] });
    },
  });

  const backfill = useBackgroundJob({
    key: "sync-history",
    start: syncHistory,
    fetchStatus: syncHistoryStatus,
    invalidate: [["opYears"], ["operations"], ["opsSummary"]],
  });

  const toggleKind = (k) =>
    setKinds((ks) => (ks.includes(k) ? ks.filter((x) => x !== k) : [...ks, k]));

  const rows = useMemo(() => {
    return (ops.data || []).filter((o) => {
      if (kinds.length && !kinds.includes(o.event_kind)) return false;
      if (search && !(o.simbolo || "").toLowerCase().includes(search.toLowerCase())) return false;
      const amount = o.monto_neto ?? o.monto_operado ?? 0;
      if (Math.abs(Number(amount)) < 0.005) return false;
      return true;
    });
  }, [ops.data, kinds, search]);

  const fmt = currency === "USD" ? formatUSD : formatARS;
  const s = sum.data || {};

  const tableFooter = useMemo(() => {
    const totalARS = rows.reduce((acc, r) => acc + (r.monto_ars ?? 0), 0);
    const totalUSD = rows.reduce((acc, r) => acc + (r.monto_usd ?? 0), 0);
    // Operaciones sin MEP histórico no tienen monto en la otra moneda: avisamos en vez de sumarlas como 0
    const sinArs = rows.filter((r) => r.monto_ars == null).length;
    const sinUsd = rows.filter((r) => r.monto_usd == null).length;
    return {
      fecha_operada: `${rows.length} op.`,
      monto_ars: formatARS(totalARS) + (sinArs ? ` (${sinArs} sin MEP)` : ""),
      monto_usd: formatUSD(totalUSD) + (sinUsd ? ` (${sinUsd} sin MEP)` : ""),
    };
  }, [rows]);
  const fxSub = "Al MEP de cada día";

  const columns = [
    {
      key: "fecha_operada",
      label: "Fecha",
      sortable: true,
      value: (r) => r.fecha_operada,
      render: (r) => formatDate(r.fecha_operada),
    },
    {
      key: "event_kind",
      label: "Tipo",
      sortable: true,
      render: (r) => (
        <span className="text-textSecondary">
          {KIND_LABEL[r.event_kind] || r.event_kind}
          {/* Sin tipo reconocido: se muestra el original de IOL para poder clasificarlo */}
          {r.event_kind === "OTRO" && r.tipo && <span className="text-textMuted"> · {r.tipo}</span>}
        </span>
      ),
    },
    {
      key: "simbolo",
      label: "Símbolo",
      sortable: true,
      render: (r) => <span className="font-medium text-text">{r.simbolo}</span>,
    },
    { key: "descripcion", label: "Descripción", className: "text-textMuted max-w-[240px] truncate" },
    {
      key: "cantidad",
      label: "Cant.",
      align: "right",
      sortable: true,
      value: (r) => Number(r.cantidad),
      render: (r) => (r.cantidad != null ? formatNumber(r.cantidad) : "—"),
    },
    {
      key: "precio",
      label: "Precio",
      align: "right",
      sortable: true,
      value: (r) => Number(r.precio),
      render: (r) => (r.precio != null ? formatNumber(r.precio) : "—"),
    },
    {
      key: "monto_ars",
      label: "Monto ARS",
      align: "right",
      sortable: true,
      value: (r) => Number(r.monto_ars ?? 0),
      render: (r) =>
        r.monto_ars != null ? (
          <span className={r.currency_kind === "ARS" ? "text-text" : "text-textMuted"}>
            {formatARS(r.monto_ars)}
          </span>
        ) : (
          <span className="text-textMuted">—</span>
        ),
    },
    {
      key: "monto_usd",
      label: "Monto USD",
      align: "right",
      sortable: true,
      value: (r) => Number(r.monto_usd ?? 0),
      render: (r) =>
        r.monto_usd != null ? (
          <span className={r.currency_kind !== "ARS" ? "text-text" : "text-textMuted"}>
            {formatUSD(r.monto_usd)}
          </span>
        ) : (
          <span className="text-textMuted">—</span>
        ),
    },
    {
      key: "currency_kind",
      label: "Moneda",
      sortable: true,
      render: (r) => <span className="text-textMuted">{CURRENCY_LABEL[r.currency_kind] || r.currency_kind}</span>,
    },
  ];

  return (
    <div>
      <PageHeader
        title="Operaciones"
        subtitle={`${rows.length} operaciones en ${year} · montos convertidos al MEP de cada día`}
        actions={
          <>
            <select
              className="input w-auto"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              aria-label="Año"
            >
              {years.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
            <input
              className="input w-52"
              placeholder="Filtrar por símbolo"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <button
              className="btn-secondary"
              onClick={backfill.run}
              disabled={backfill.running || sync.isPending}
              title="Trae de IOL las operaciones, rentas, dividendos y amortizaciones de todos los años"
            >
              {backfill.running ? "Trayendo historial…" : "Traer historial"}
            </button>
            <button
              className="btn-primary"
              onClick={() => sync.mutate()}
              disabled={sync.isPending || backfill.running}
            >
              {sync.isPending ? "Sincronizando…" : "Sincronizar"}
            </button>
          </>
        }
      />

      <div className="space-y-4">
        {backfill.running && (
          <div className="notice" role="status">
            <span>
              Trayendo el historial de IOL año por año{backfill.step ? `: ${backfill.step}` : ""}. Puede tardar
              unos minutos; podés seguir usando la app.
            </span>
          </div>
        )}
        {backfill.result && (
          <div className="notice" role="status">
            <span>
              {backfill.result.found
                ? `Historial completo: ${backfill.result.found} operaciones desde ${backfill.result.oldest}. Elegí el año arriba.`
                : "IOL no devolvió operaciones de años anteriores."}
            </span>
          </div>
        )}
        {backfill.error && (
          <div className="notice" role="alert">
            <span className="text-danger font-medium">Error</span>
            <span>
              No se pudo terminar de traer el historial ({backfill.error}). Lo ya traído quedó guardado; podés
              volver a intentarlo.
            </span>
          </div>
        )}
        {s.fx_missing_count > 0 && (
          <div className="notice" role="status">
            <span className="text-warn font-medium">Atención</span>
            <span>
              {s.fx_missing_count} operación{s.fx_missing_count !== 1 ? "es" : ""} sin cotización MEP
              histórica. Sincronizá para completarlas.
            </span>
          </div>
        )}

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          <KpiCard
            label="Compras"
            value={fmt(currency === "USD" ? s.total_compras_usd : s.total_compras_ars)}
            sub={fxSub}
          />
          <KpiCard
            label="Ventas"
            value={fmt(currency === "USD" ? s.total_ventas_usd : s.total_ventas_ars)}
            sub={fxSub}
          />
          <KpiCard
            label="Renta"
            value={fmt(currency === "USD" ? s.total_renta_usd : s.total_renta_ars)}
            sub={fxSub}
          />
          <KpiCard
            label="Amortizaciones"
            value={fmt(currency === "USD" ? s.total_amortizaciones_usd : s.total_amortizaciones_ars)}
            sub={fxSub}
          />
          <KpiCard
            label="Dividendos"
            value={fmt(currency === "USD" ? s.total_dividendos_usd : s.total_dividendos_ars)}
            sub={fxSub}
          />
        </div>

        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filtrar por tipo">
          {KINDS.map((k) => (
            <button
              key={k}
              onClick={() => toggleKind(k)}
              aria-pressed={kinds.includes(k)}
              className={`h-7 px-2.5 rounded-md border text-xs font-medium transition-colors ${
                kinds.includes(k)
                  ? "border-text bg-text text-bg"
                  : "border-border text-textMuted hover:text-text"
              }`}
            >
              {KIND_LABEL[k]}
            </button>
          ))}
          {kinds.length > 0 && (
            <button onClick={() => setKinds([])} className="btn-ghost h-7 px-2 text-xs">
              Limpiar
            </button>
          )}
        </div>

        {ops.isLoading ? (
          <LoadingSpinner />
        ) : (
          <DataTable columns={columns} rows={rows} footer={tableFooter} emptyText="Sin operaciones." />
        )}
      </div>
    </div>
  );
}
