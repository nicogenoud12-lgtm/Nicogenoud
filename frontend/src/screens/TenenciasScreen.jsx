import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { getHoldings } from "../api/portfolio";
import DataTable from "../components/DataTable.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import { formatARS, formatNumber, formatUSD } from "../utils/format";
import { useUiStore } from "../store/uiStore";

const CLASES = ["Todos", "CEDEAR", "Acción", "Bono", "ON", "Letra", "FCI", "Otro"];

export default function TenenciasScreen() {
  const currency = useUiStore((s) => s.currency);
  const qc = useQueryClient();
  const [clase, setClase] = useState("Todos");
  const [search, setSearch] = useState("");

  const q = useQuery({ queryKey: ["holdings"], queryFn: () => getHoldings(false) });
  const refresh = useMutation({
    mutationFn: () => getHoldings(true),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["holdings"] }),
  });

  const rows = useMemo(() => {
    const list = q.data || [];
    return list.filter((r) => {
      if (clase !== "Todos" && r.clase !== clase) return false;
      if (search) {
        const s = search.toLowerCase();
        if (
          !(r.simbolo || "").toLowerCase().includes(s) &&
          !(r.descripcion || "").toLowerCase().includes(s)
        )
          return false;
      }
      return true;
    });
  }, [q.data, clase, search]);

  const fmt = currency === "USD" ? formatUSD : formatARS;

  const totalFiltrado = useMemo(
    () =>
      rows.reduce(
        (acc, r) =>
          acc + Number((currency === "USD" ? r.valuacion_usd : r.valuacion_ars) || 0),
        0,
      ),
    [rows, currency],
  );

  const columns = [
    { key: "simbolo", label: "Símbolo", sortable: true },
    { key: "clase", label: "Clase", sortable: true, render: (r) => <span className="chip">{r.clase}</span> },
    { key: "descripcion", label: "Descripción", sortable: true },
    {
      key: "cantidad",
      label: "Cant.",
      align: "right",
      sortable: true,
      value: (r) => Number(r.cantidad),
      render: (r) => formatNumber(r.cantidad),
    },
    {
      key: "ppc",
      label: "PPC",
      align: "right",
      sortable: true,
      value: (r) => Number(r.ppc),
      render: (r) => (r.ppc != null ? formatNumber(r.ppc) : "—"),
    },
    {
      key: "ultimo_precio",
      label: "Último",
      align: "right",
      sortable: true,
      value: (r) => Number(r.ultimo_precio),
      render: (r) => (r.ultimo_precio != null ? formatNumber(r.ultimo_precio) : "—"),
    },
    {
      key: "valuacion",
      label: `Valuación (${currency})`,
      align: "right",
      sortable: true,
      value: (r) => Number(currency === "USD" ? r.valuacion_usd : r.valuacion_ars),
      render: (r) => fmt(currency === "USD" ? r.valuacion_usd : r.valuacion_ars),
    },
    {
      key: "ganancia_porcentaje",
      label: "G/P %",
      align: "right",
      sortable: true,
      value: (r) => Number(r.ganancia_porcentaje),
      render: (r) => {
        const v = Number(r.ganancia_porcentaje || 0);
        return (
          <span className={v >= 0 ? "text-success" : "text-danger"}>{v.toFixed(2)}%</span>
        );
      },
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold mr-auto">Tenencias</h1>
        <input
          className="input max-w-xs"
          placeholder="Buscar símbolo o descripción"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button
          className="btn-primary"
          onClick={() => refresh.mutate()}
          disabled={refresh.isPending}
        >
          {refresh.isPending ? "Actualizando…" : "↻ Actualizar"}
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {CLASES.map((c) => (
          <button
            key={c}
            onClick={() => setClase(c)}
            className={`chip ${
              clase === c ? "bg-accent text-white border-accent" : "cursor-pointer"
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      <div className="card p-3 flex flex-wrap items-baseline justify-between gap-2">
        <div className="text-xs uppercase tracking-wide text-textMuted">
          Total {clase === "Todos" ? "" : clase} · {rows.length}{" "}
          {rows.length === 1 ? "tenencia" : "tenencias"}
        </div>
        <div className="text-lg font-semibold tabular-nums">{fmt(totalFiltrado)}</div>
      </div>

      {q.isLoading ? <LoadingSpinner /> : <DataTable columns={columns} rows={rows} />}
    </div>
  );
}
