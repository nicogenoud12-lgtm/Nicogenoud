import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { getHoldings } from "../api/portfolio";
import DataTable from "../components/DataTable.jsx";
import Delta from "../components/Delta.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import PageHeader from "../components/PageHeader.jsx";
import { colorFor, useChartTokens } from "../components/charts/chartTheme";
import { formatARS, formatNumber, formatUSD } from "../utils/format";
import { useUiStore } from "../store/uiStore";

const CLASES = ["Todos", "CEDEAR", "Acción", "Bono", "ON", "Letra", "FCI", "Otro"];

export default function TenenciasScreen() {
  const currency = useUiStore((s) => s.currency);
  const t = useChartTokens();
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
    {
      key: "simbolo",
      label: "Símbolo",
      sortable: true,
      render: (r) => <span className="font-medium text-text">{r.simbolo}</span>,
    },
    {
      key: "clase",
      label: "Clase",
      sortable: true,
      render: (r) => (
        <span className="inline-flex items-center gap-2 text-textSecondary">
          <span
            className="h-2 w-2 rounded-full"
            style={{ background: colorFor(r.clase, [], t.categorical) || t.axis }}
          />
          {r.clase}
        </span>
      ),
    },
    {
      key: "descripcion",
      label: "Descripción",
      sortable: true,
      className: "text-textMuted max-w-[260px] truncate",
    },
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
      render: (r) => <Delta value={Number(r.ganancia_porcentaje || 0)} />,
    },
  ];

  return (
    <div>
      <PageHeader
        title="Tenencias"
        subtitle={`${rows.length} ${rows.length === 1 ? "tenencia" : "tenencias"}${
          clase === "Todos" ? "" : ` · ${clase}`
        } · ${fmt(totalFiltrado)}`}
        actions={
          <>
            <input
              className="input w-64"
              placeholder="Buscar símbolo o descripción"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <button className="btn-secondary" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
              {refresh.isPending ? "Actualizando…" : "Actualizar"}
            </button>
          </>
        }
      />

      <div className="mb-4 overflow-x-auto">
        <div className="segmented" role="group" aria-label="Filtrar por clase">
          {CLASES.map((c) => (
            <button
              key={c}
              onClick={() => setClase(c)}
              aria-pressed={clase === c}
              className={`segmented-item ${clase === c ? "segmented-item-active" : ""}`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {q.isLoading ? <LoadingSpinner /> : <DataTable columns={columns} rows={rows} emptyText="Sin tenencias." />}
    </div>
  );
}
