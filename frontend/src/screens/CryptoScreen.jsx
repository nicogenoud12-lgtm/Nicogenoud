import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  createCryptoHolding,
  deleteCryptoHolding,
  listCryptoHoldings,
  updateCryptoHolding,
} from "../api/crypto";
import KpiCard from "../components/KpiCard.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import { formatNumber, formatUSD } from "../utils/format";

const EMPTY_FORM = {
  symbol: "",
  name: "",
  cantidad: "",
  costo_usd_unit: "",
  exchange: "",
  notas: "",
};

function toNumberOrNull(v) {
  if (v === "" || v == null) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export default function CryptoScreen() {
  const qc = useQueryClient();
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [showForm, setShowForm] = useState(false);
  const [search, setSearch] = useState("");

  const q = useQuery({ queryKey: ["crypto-holdings"], queryFn: listCryptoHoldings });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["crypto-holdings"] });

  const createM = useMutation({
    mutationFn: createCryptoHolding,
    onSuccess: () => {
      invalidate();
      resetForm();
    },
  });
  const updateM = useMutation({
    mutationFn: ({ id, payload }) => updateCryptoHolding(id, payload),
    onSuccess: () => {
      invalidate();
      resetForm();
    },
  });
  const deleteM = useMutation({
    mutationFn: deleteCryptoHolding,
    onSuccess: invalidate,
  });

  function resetForm() {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setShowForm(false);
  }

  function startEdit(h) {
    setEditingId(h.id);
    setForm({
      symbol: h.symbol || "",
      name: h.name || "",
      cantidad: h.cantidad ?? "",
      costo_usd_unit: h.costo_usd_unit ?? "",
      exchange: h.exchange || "",
      notas: h.notas || "",
    });
    setShowForm(true);
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!form.symbol.trim()) return;
    const cantidad = toNumberOrNull(form.cantidad);
    if (cantidad == null) return;
    const payload = {
      symbol: form.symbol.trim().toUpperCase(),
      name: form.name.trim() || null,
      cantidad,
      costo_usd_unit: toNumberOrNull(form.costo_usd_unit),
      exchange: form.exchange.trim() || null,
      notas: form.notas.trim() || null,
    };
    if (editingId != null) {
      updateM.mutate({ id: editingId, payload });
    } else {
      createM.mutate(payload);
    }
  }

  const rows = useMemo(() => {
    const list = q.data || [];
    if (!search) return list;
    const s = search.toLowerCase();
    return list.filter(
      (r) =>
        (r.symbol || "").toLowerCase().includes(s) ||
        (r.name || "").toLowerCase().includes(s) ||
        (r.exchange || "").toLowerCase().includes(s),
    );
  }, [q.data, search]);

  const totals = useMemo(() => {
    let costo = 0;
    let conCosto = 0;
    for (const r of rows) {
      const c = Number(r.costo_usd_unit ?? 0);
      const cant = Number(r.cantidad ?? 0);
      if (r.costo_usd_unit != null && Number.isFinite(c) && Number.isFinite(cant)) {
        costo += c * cant;
        conCosto += 1;
      }
    }
    return { costo, conCosto, count: rows.length };
  }, [rows]);

  const saving = createM.isPending || updateM.isPending;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold mr-auto">Crypto</h1>
        <input
          className="input max-w-xs"
          placeholder="Buscar símbolo o exchange"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button
          className="btn-primary"
          onClick={() => {
            if (showForm && editingId == null) {
              resetForm();
            } else {
              setEditingId(null);
              setForm(EMPTY_FORM);
              setShowForm(true);
            }
          }}
        >
          {showForm && editingId == null ? "Cerrar" : "+ Agregar tenencia"}
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <KpiCard label="Tenencias" value={formatNumber(totals.count)} />
        <KpiCard
          label="Costo total (USD)"
          value={formatUSD(totals.costo)}
          sub={
            totals.conCosto < totals.count
              ? `${totals.conCosto}/${totals.count} con costo cargado`
              : null
          }
        />
        <KpiCard
          label="Valor en vivo"
          value="—"
          sub="Próximamente (API de cotizaciones)"
        />
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="card p-4 grid grid-cols-1 md:grid-cols-6 gap-3"
        >
          <div className="md:col-span-1">
            <div className="label mb-1">Símbolo *</div>
            <input
              className="input uppercase"
              placeholder="BTC"
              value={form.symbol}
              onChange={(e) => setForm({ ...form, symbol: e.target.value })}
              required
              autoFocus
            />
          </div>
          <div className="md:col-span-2">
            <div className="label mb-1">Nombre</div>
            <input
              className="input"
              placeholder="Bitcoin"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div className="md:col-span-1">
            <div className="label mb-1">Cantidad *</div>
            <input
              className="input"
              type="number"
              step="any"
              min="0"
              placeholder="0.5"
              value={form.cantidad}
              onChange={(e) => setForm({ ...form, cantidad: e.target.value })}
              required
            />
          </div>
          <div className="md:col-span-1">
            <div className="label mb-1">Costo unit. (USD)</div>
            <input
              className="input"
              type="number"
              step="any"
              min="0"
              placeholder="65000"
              value={form.costo_usd_unit}
              onChange={(e) => setForm({ ...form, costo_usd_unit: e.target.value })}
            />
          </div>
          <div className="md:col-span-1">
            <div className="label mb-1">Exchange / wallet</div>
            <input
              className="input"
              placeholder="Binance"
              value={form.exchange}
              onChange={(e) => setForm({ ...form, exchange: e.target.value })}
            />
          </div>
          <div className="md:col-span-6">
            <div className="label mb-1">Notas</div>
            <input
              className="input"
              placeholder="Opcional"
              value={form.notas}
              onChange={(e) => setForm({ ...form, notas: e.target.value })}
            />
          </div>
          <div className="md:col-span-6 flex gap-2 justify-end">
            <button type="button" className="btn-secondary" onClick={resetForm}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? "Guardando…" : editingId != null ? "Guardar cambios" : "Agregar"}
            </button>
          </div>
        </form>
      )}

      {q.isLoading ? (
        <LoadingSpinner />
      ) : rows.length === 0 ? (
        <div className="card p-6 text-center text-textMuted">
          {search
            ? "Sin resultados para la búsqueda."
            : 'Todavía no cargaste tenencias. Tocá "+ Agregar tenencia".'}
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surfaceAlt text-textMuted text-xs uppercase">
              <tr>
                <th className="px-3 py-2 text-left">Símbolo</th>
                <th className="px-3 py-2 text-left">Nombre</th>
                <th className="px-3 py-2 text-right">Cantidad</th>
                <th className="px-3 py-2 text-right">Costo unit. (USD)</th>
                <th className="px-3 py-2 text-right">Costo total (USD)</th>
                <th className="px-3 py-2 text-left">Exchange</th>
                <th className="px-3 py-2 text-left">Notas</th>
                <th className="px-3 py-2 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const total =
                  r.costo_usd_unit != null
                    ? Number(r.costo_usd_unit) * Number(r.cantidad || 0)
                    : null;
                return (
                  <tr
                    key={r.id}
                    className="border-t border-border hover:bg-surfaceAlt/50"
                  >
                    <td className="px-3 py-2 font-medium">{r.symbol}</td>
                    <td className="px-3 py-2 text-textMuted">{r.name || "—"}</td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatNumber(r.cantidad)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {r.costo_usd_unit != null ? formatUSD(r.costo_usd_unit) : "—"}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {total != null ? formatUSD(total) : "—"}
                    </td>
                    <td className="px-3 py-2 text-textMuted">{r.exchange || "—"}</td>
                    <td className="px-3 py-2 text-textMuted max-w-xs truncate">
                      {r.notas || "—"}
                    </td>
                    <td className="px-3 py-2 text-right whitespace-nowrap">
                      <button
                        className="text-accent hover:underline mr-3"
                        onClick={() => startEdit(r)}
                      >
                        Editar
                      </button>
                      <button
                        className="text-danger hover:underline disabled:opacity-50"
                        disabled={deleteM.isPending}
                        onClick={() => {
                          if (confirm(`¿Eliminar ${r.symbol}?`)) deleteM.mutate(r.id);
                        }}
                      >
                        Eliminar
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
