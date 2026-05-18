import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { listOperations, operationsSummary, syncOperations } from "../api/operations";
import DataTable from "../components/DataTable.jsx";
import KpiCard from "../components/KpiCard.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import { formatARS, formatDate, formatNumber, formatUSD } from "../utils/format";
import { useUiStore } from "../store/uiStore";

const KINDS = ["COMPRA", "VENTA", "SUSCRIPCION", "RESCATE", "RENTA", "AMORTIZACION", "DIVIDENDO"];

export default function OperacionesScreen() {
  const currency = useUiStore((s) => s.currency);
  const qc = useQueryClient();
  const [year] = useState(2026);
  const [kinds, setKinds] = useState(["COMPRA", "VENTA", "SUSCRIPCION", "RESCATE"]);
  const [search, setSearch] = useState("");

  const ops = useQuery({
    queryKey: ["operations", year],
    queryFn: () => listOperations({ year }),
  });
  const sum = useQuery({
    queryKey: ["opsSummary", year],
    queryFn: () => operationsSummary(year),
  });
  const sync = useMutation({
    mutationFn: () => syncOperations(year),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["operations", year] });
      qc.invalidateQueries({ queryKey: ["opsSummary", year] });
    },
  });

  const toggleKind = (k) =>
    setKinds((ks) => (ks.includes(k) ? ks.filter((x) => x !== k) : [...ks, k]));

  const rows = useMemo(() => {
    return (ops.data || []).filter((o) => {
      if (kinds.length && !kinds.includes(o.event_kind)) return false;
      if (search && !(o.simbolo || "").toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [ops.data, kinds, search]);

  const fmt = currency === "USD" ? formatUSD : formatARS;
  const s = sum.data || {};
  const fxSub = "convertido a MEP del día";

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
        <span
          className={`chip ${
            r.event_kind === "COMPRA"
              ? "border-accent/30 text-accent"
              : r.event_kind === "VENTA"
                ? "border-success/30 text-success"
                : ""
          }`}
        >
          {r.event_kind}
        </span>
      ),
    },
    { key: "simbolo", label: "Símbolo", sortable: true },
    { key: "descripcion", label: "Descripción" },
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
      key: "monto_neto",
      label: "Monto neto",
      align: "right",
      sortable: true,
      value: (r) => Number(r.monto_neto || r.monto_operado || 0),
      render: (r) => fmt(r.monto_neto != null ? r.monto_neto : r.monto_operado),
    },
    {
      key: "currency_kind",
      label: "Moneda",
      sortable: true,
      render: (r) => <span className="text-xs text-textMuted">{r.currency_kind}</span>,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold mr-auto">Operaciones {year}</h1>
        <input
          className="input max-w-xs"
          placeholder="Filtrar por símbolo"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button
          className="btn-primary"
          onClick={() => sync.mutate()}
          disabled={sync.isPending}
        >
          {sync.isPending ? "Sincronizando…" : "↻ Sincronizar"}
        </button>
      </div>

      {s.fx_missing_count > 0 && (
        <div className="text-xs text-amber-400 bg-amber-400/10 border border-amber-400/20 rounded px-3 py-1.5">
          ⚠ {s.fx_missing_count} operación{s.fx_missing_count !== 1 ? "es" : ""} sin tasa MEP histórica — sincronizá para completar
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
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
          label="Dividendos"
          value={fmt(currency === "USD" ? s.total_dividendos_usd : s.total_dividendos_ars)}
          sub={fxSub}
        />
      </div>

      <div className="flex flex-wrap gap-2">
        {KINDS.map((k) => (
          <button
            key={k}
            onClick={() => toggleKind(k)}
            className={`chip ${
              kinds.includes(k) ? "bg-accent text-white border-accent" : "cursor-pointer"
            }`}
          >
            {k}
          </button>
        ))}
      </div>

      {ops.isLoading ? <LoadingSpinner /> : <DataTable columns={columns} rows={rows} />}
    </div>
  );
}
