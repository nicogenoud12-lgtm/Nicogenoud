import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { periodToDays } from "../utils/periods";
import {
  backfillCryptoSnapshots,
  createCryptoHolding,
  deleteCryptoHolding,
  deleteCryptoSale,
  getCryptoReport,
  listCryptoHoldings,
  listCryptoSales,
  listCryptoSnapshots,
  searchCoins,
  sellCryptoHolding,
  updateCryptoHolding,
} from "../api/crypto";
import AssetDonutChart from "../components/charts/AssetDonutChart.jsx";
import PortfolioLineChart from "../components/charts/PortfolioLineChart.jsx";
import KpiCard from "../components/KpiCard.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import { useUiStore } from "../store/uiStore";
import { formatARS, formatDate, formatNumber, formatUSD } from "../utils/format";

// CoinGecko ID → CoinMarketCap URL slug (only exceptions; most match exactly)
const CMC_SLUG_OVERRIDES = {
  "binancecoin":       "binance-coin",
  "polkadot":          "polkadot-new",
  "avalanche-2":       "avalanche",
  "matic-network":     "polygon",
  "near":              "near-protocol",
  "hedera-hashgraph":  "hedera",
  "dai":               "multi-collateral-dai",
  "dogwifcoin":        "dogwifhat",
  "internet-computer": "internet-computer",
};

function cmcUrl(coingeckoId) {
  if (!coingeckoId) return null;
  const slug = CMC_SLUG_OVERRIDES[coingeckoId] || coingeckoId;
  return `https://coinmarketcap.com/es/currencies/${slug}/`;
}

const EMPTY_FORM = {
  symbol: "",
  name: "",
  coingecko_id: "",
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

function CoinPicker({ value, onPick }) {
  const [q, setQ] = useState(value || "");
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef(null);

  useEffect(() => {
    setQ(value || "");
  }, [value]);

  useEffect(() => {
    if (!q || q.trim().length < 1) {
      setResults([]);
      return;
    }
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await searchCoins(q.trim());
        setResults(data || []);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    function onDoc(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <div className="relative" ref={boxRef}>
      <input
        className="input"
        placeholder="Buscar (BTC, ethereum, solana…)"
        value={q}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
      />
      {open && (results.length > 0 || loading) && (
        <div className="absolute z-20 mt-1 w-full card max-h-72 overflow-y-auto">
          {loading && (
            <div className="px-3 py-2 text-xs text-textMuted">Buscando…</div>
          )}
          {results.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => {
                onPick(c);
                setOpen(false);
                setQ("");
              }}
              className="w-full text-left px-3 py-2 hover:bg-surfaceAlt flex items-center gap-2 text-sm"
            >
              {c.thumb && (
                <img src={c.thumb} alt="" className="h-5 w-5 rounded-full" />
              )}
              <span className="font-medium">{c.symbol}</span>
              <span className="text-textMuted">{c.name}</span>
              {c.market_cap_rank && (
                <span className="ml-auto text-xs text-textMuted">
                  #{c.market_cap_rank}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function SellModal({ item, onClose, onConfirm, pending, error }) {
  const held = Number(item.cantidad || 0);
  const livePrice = item.price_usd != null ? Number(item.price_usd) : null;
  const costUnit = item.costo_usd_unit != null ? Number(item.costo_usd_unit) : null;

  const [qty, setQty] = useState(String(held));
  const [price, setPrice] = useState(livePrice != null ? String(livePrice) : "");
  const [notas, setNotas] = useState("");

  const qtyN = toNumberOrNull(qty);
  const priceN = toNumberOrNull(price);
  const validQty = qtyN != null && qtyN > 0 && qtyN <= held + 1e-9;
  const validPrice = priceN != null && priceN > 0;

  // Preview del P&L realizado contra el costo promedio actual.
  const proceeds = validQty && validPrice ? qtyN * priceN : null;
  const costTotal = validQty && costUnit != null ? qtyN * costUnit : null;
  const pnl = proceeds != null && costTotal != null ? proceeds - costTotal : null;
  const pnlPct = pnl != null && costTotal ? (pnl / costTotal) * 100 : null;

  function submit(e) {
    e.preventDefault();
    if (!validQty || !validPrice) return;
    onConfirm({
      cantidad: qtyN,
      price_usd: priceN,
      notas: notas.trim() || null,
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="card w-full max-w-md p-5 space-y-4">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">Vender {item.symbol}</h2>
          <button
            className="ml-auto text-textMuted hover:text-text"
            onClick={onClose}
            type="button"
          >
            ✕
          </button>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <div>
            <div className="label mb-1 flex items-center justify-between">
              <span>Cantidad a vender</span>
              <button
                type="button"
                className="text-xs text-accent hover:underline"
                onClick={() => setQty(String(held))}
              >
                Máx: {formatNumber(held)}
              </button>
            </div>
            <input
              className="input"
              type="number"
              step="any"
              min="0"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              required
            />
            {qtyN != null && qtyN > held + 1e-9 && (
              <div className="text-xs text-danger mt-1">
                Supera tu tenencia ({formatNumber(held)}).
              </div>
            )}
          </div>

          <div>
            <div className="label mb-1 flex items-center justify-between">
              <span>Precio de venta (USD / unidad)</span>
              {livePrice != null && (
                <button
                  type="button"
                  className="text-xs text-accent hover:underline"
                  onClick={() => setPrice(String(livePrice))}
                >
                  En vivo: {formatUSD(livePrice)}
                </button>
              )}
            </div>
            <input
              className="input"
              type="number"
              step="any"
              min="0"
              placeholder="Precio en USD"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              required
            />
          </div>

          <div>
            <div className="label mb-1">Notas</div>
            <input
              className="input"
              placeholder="Opcional"
              value={notas}
              onChange={(e) => setNotas(e.target.value)}
            />
          </div>

          <div className="rounded-lg bg-surfaceAlt p-3 text-sm space-y-1">
            <div className="flex justify-between">
              <span className="text-textMuted">Ingreso por venta</span>
              <span className="tabular-nums">
                {proceeds != null ? formatUSD(proceeds) : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-textMuted">Costo (promedio)</span>
              <span className="tabular-nums">
                {costTotal != null ? formatUSD(costTotal) : "—"}
              </span>
            </div>
            <div className="flex justify-between font-medium">
              <span className="text-textMuted">P&L realizado</span>
              <span
                className={`tabular-nums ${
                  pnl == null
                    ? ""
                    : pnl >= 0
                      ? "text-success"
                      : "text-danger"
                }`}
              >
                {pnl != null ? formatUSD(pnl) : "—"}
                {pnlPct != null && (
                  <> ({pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%)</>
                )}
              </span>
            </div>
            {qtyN != null && qtyN < held - 1e-9 && (
              <div className="text-xs text-textMuted pt-1">
                Quedan {formatNumber(held - qtyN)} {item.symbol} en cartera.
              </div>
            )}
          </div>

          {error && <div className="text-sm text-danger">{error}</div>}

          <div className="flex gap-2 justify-end">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancelar
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={pending || !validQty || !validPrice}
            >
              {pending ? "Vendiendo…" : "Confirmar venta"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function CryptoScreen() {
  const qc = useQueryClient();
  const currency = useUiStore((s) => s.currency);
  const fmt = currency === "USD" ? formatUSD : formatARS;

  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [showForm, setShowForm] = useState(false);
  const [snapPeriod, setSnapPeriod] = useState("MAX");
  const snapDays = periodToDays(snapPeriod);

  const holdings = useQuery({
    queryKey: ["crypto-holdings"],
    queryFn: listCryptoHoldings,
  });
  const report = useQuery({
    queryKey: ["crypto-report"],
    queryFn: getCryptoReport,
    staleTime: 0,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  });
  const snaps = useQuery({
    queryKey: ["crypto-snapshots", snapDays],
    queryFn: () => listCryptoSnapshots(snapDays),
  });
  const sales = useQuery({
    queryKey: ["crypto-sales"],
    queryFn: listCryptoSales,
  });

  const [sellTarget, setSellTarget] = useState(null);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["crypto-holdings"] });
    qc.invalidateQueries({ queryKey: ["crypto-report"] });
    qc.invalidateQueries({ queryKey: ["crypto-snapshots"] });
    qc.invalidateQueries({ queryKey: ["crypto-sales"] });
  };

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
  const sellM = useMutation({
    mutationFn: ({ id, payload }) => sellCryptoHolding(id, payload),
    onSuccess: () => {
      invalidate();
      setSellTarget(null);
    },
  });
  const deleteSaleM = useMutation({
    mutationFn: deleteCryptoSale,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["crypto-sales"] }),
  });
  const backfillM = useMutation({
    mutationFn: () => backfillCryptoSnapshots(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["crypto-snapshots"] });
    },
  });

  const [sortKey, setSortKey] = useState("value_usd");
  const [sortDir, setSortDir] = useState("desc");
  function toggleSort(key) {
    if (sortKey === key) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }
  const sortIndicator = (key) =>
    sortKey === key ? (sortDir === "desc" ? " ↓" : " ↑") : "";

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
      coingecko_id: h.coingecko_id || "",
      cantidad: h.cantidad ?? "",
      costo_usd_unit: h.costo_usd_unit ?? "",
      exchange: h.exchange || "",
      notas: h.notas || "",
    });
    setShowForm(true);
  }

  function handlePick(coin) {
    setForm((f) => ({
      ...f,
      symbol: coin.symbol || f.symbol,
      name: coin.name || f.name,
      coingecko_id: coin.id || f.coingecko_id,
    }));
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!form.symbol.trim()) return;
    const cantidad = toNumberOrNull(form.cantidad);
    if (cantidad == null) return;
    const payload = {
      symbol: form.symbol.trim().toUpperCase(),
      name: form.name.trim() || null,
      coingecko_id: form.coingecko_id.trim() || null,
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

  const r = report.data;
  const items = r?.items || [];

  const tableRows = useMemo(() => {
    const byId = new Map(items.map((i) => [i.id, i]));
    const rows = (holdings.data || []).map((h) => {
      const it = byId.get(h.id);
      if (it) return it;
      const cost =
        h.costo_usd_unit != null ? Number(h.costo_usd_unit) * Number(h.cantidad || 0) : null;
      return {
        id: h.id,
        symbol: h.symbol,
        name: h.name,
        coingecko_id: h.coingecko_id,
        cantidad: Number(h.cantidad || 0),
        costo_usd_unit: h.costo_usd_unit != null ? Number(h.costo_usd_unit) : null,
        costo_total_usd: cost,
        price_usd: null,
        price_ars: null,
        value_usd: null,
        value_ars: null,
        pnl_usd: null,
        pnl_pct: null,
        change_24h_pct: null,
        change_7d_pct: null,
        pct_portfolio: 0,
        exchange: h.exchange,
        has_price: false,
      };
    });

    const dir = sortDir === "desc" ? -1 : 1;
    const sorted = [...rows].sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      // Nulls go to the bottom regardless of direction
      const aNull = va == null;
      const bNull = vb == null;
      if (aNull && bNull) return 0;
      if (aNull) return 1;
      if (bNull) return -1;
      if (typeof va === "string" && typeof vb === "string") {
        return va.localeCompare(vb) * dir;
      }
      return (Number(va) - Number(vb)) * dir;
    });
    return sorted;
  }, [holdings.data, items, sortKey, sortDir]);

  const distribution = useMemo(
    () =>
      items
        .filter((i) => i.value_usd && i.value_usd > 0)
        .map((i) => ({
          clase: i.symbol,
          valor_usd: i.value_usd || 0,
          valor_ars: i.value_ars || 0,
          pct: i.pct_portfolio || 0,
        })),
    [items],
  );

  const movers = useMemo(
    () =>
      items
        .filter((i) => i.change_24h_pct != null)
        .slice()
        .sort(
          (a, b) => Math.abs(b.change_24h_pct) - Math.abs(a.change_24h_pct),
        )
        .slice(0, 5),
    [items],
  );

  const totalValue = currency === "USD" ? r?.total_value_usd : r?.total_value_ars;
  const totalCost =
    currency === "USD"
      ? r?.total_cost_usd
      : r?.total_cost_usd && r?.ars_rate
        ? r.total_cost_usd * r.ars_rate
        : 0;
  const pnlValue =
    currency === "USD"
      ? r?.pnl_total_usd
      : r?.pnl_total_usd && r?.ars_rate
        ? r.pnl_total_usd * r.ars_rate
        : 0;

  const saving = createM.isPending || updateM.isPending;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold mr-auto">Crypto</h1>
        <button
          className="btn-secondary text-xs"
          onClick={() => backfillM.mutate()}
          disabled={backfillM.isPending}
          title="Recalcula la evolución diaria desde el 1° de enero usando precios históricos de CoinGecko y tus tenencias actuales."
        >
          {backfillM.isPending ? "Recalculando…" : "↻ Recalcular evolución"}
        </button>
        {report.isFetching && (
          <span className="text-xs text-textMuted">Actualizando…</span>
        )}
        {r?.fetched_at && !report.isFetching && (
          <span className="text-xs text-textMuted">
            {new Date(r.fetched_at).toLocaleTimeString("es-AR")}
          </span>
        )}
      </div>
      {backfillM.isSuccess && backfillM.data && (
        <div className="card p-3 text-sm">
          Evolución recalculada: {backfillM.data.days} días desde {backfillM.data.since}
          {backfillM.data.failed_symbols?.length > 0 && (
            <> · Sin historial: {backfillM.data.failed_symbols.join(", ")}</>
          )}
        </div>
      )}

      {r?.fetch_error && (
        <div className="card p-3 text-sm border-warn/30 text-warn">
          No se pudieron obtener cotizaciones: {r.fetch_error}. Se muestran los
          datos por costo cargado.
        </div>
      )}
      {r?.missing_coingecko?.length > 0 && (
        <div className="card p-3 text-sm text-textMuted">
          Sin precio en vivo: <strong>{r.missing_coingecko.join(", ")}</strong>.
          Editá la tenencia y elegí la moneda desde el buscador para asignarle un
          ID de CoinGecko.
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard
          label={`Valor (${currency})`}
          value={fmt(totalValue || 0)}
          sub={
            r?.ars_rate
              ? `${r.dolar_source}: ${Number(r.ars_rate).toFixed(2)}`
              : null
          }
        />
        <KpiCard label={`Costo (${currency})`} value={fmt(totalCost || 0)} />
        <KpiCard
          label="P&L"
          value={fmt(pnlValue || 0)}
          tone={(pnlValue || 0) >= 0 ? "positive" : "negative"}
        />
        <KpiCard
          label="P&L %"
          value={
            r?.pnl_total_pct != null ? `${r.pnl_total_pct.toFixed(2)}%` : "—"
          }
          tone={(r?.pnl_total_pct || 0) >= 0 ? "positive" : "negative"}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <PortfolioLineChart
            data={snaps.data || []}
            period={snapPeriod}
            onPeriodChange={setSnapPeriod}
            title="Evolución Crypto"
          />
        </div>
        {distribution.length > 0 ? (
          <AssetDonutChart data={distribution} />
        ) : (
          <div className="card p-4 flex items-center justify-center text-sm text-textMuted">
            Cargá tenencias con precio en vivo para ver la distribución.
          </div>
        )}
      </div>

      <div className="card p-4">
        <div className="label mb-3">Top movers · 24h</div>
        {movers.length === 0 ? (
          <div className="text-sm text-textMuted">
            Sin datos de variación. Asegurate de que tus tenencias tengan asignado
            un ID de CoinGecko.
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {movers.map((m) => (
              <li
                key={m.id}
                className="py-2 flex items-center justify-between gap-2"
              >
                <div className="min-w-0">
                  <div className="font-medium">{m.symbol}</div>
                  <div className="text-xs text-textMuted truncate">
                    {m.name || m.coingecko_id}
                  </div>
                </div>
                <div className="text-right tabular-nums">
                  <div>{fmt(currency === "USD" ? m.value_usd : m.value_ars)}</div>
                  <div
                    className={`text-xs ${
                      (m.change_24h_pct || 0) >= 0 ? "text-success" : "text-danger"
                    }`}
                  >
                    {m.change_24h_pct >= 0 ? "+" : ""}
                    {m.change_24h_pct.toFixed(2)}%
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="card p-4 space-y-3">
        <div className="flex items-center gap-2">
          <div className="label">Mis tenencias</div>
          <button
            className="ml-auto btn-primary"
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

        {showForm && (
          <form
            onSubmit={handleSubmit}
            className="grid grid-cols-1 md:grid-cols-6 gap-3 border-t border-border pt-3"
          >
            <div className="md:col-span-3">
              <div className="label mb-1">Buscar en CoinGecko</div>
              <CoinPicker onPick={handlePick} />
              {form.coingecko_id && (
                <div className="text-xs text-textMuted mt-1">
                  ID: <code>{form.coingecko_id}</code>
                </div>
              )}
            </div>
            <div className="md:col-span-1">
              <div className="label mb-1">Símbolo *</div>
              <input
                className="input uppercase"
                placeholder="BTC"
                value={form.symbol}
                onChange={(e) => setForm({ ...form, symbol: e.target.value })}
                required
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
            <div className="md:col-span-2">
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
            <div className="md:col-span-2">
              <div className="label mb-1">Costo unit. (USD)</div>
              <input
                className="input"
                type="number"
                step="any"
                min="0"
                placeholder="65000"
                value={form.costo_usd_unit}
                onChange={(e) =>
                  setForm({ ...form, costo_usd_unit: e.target.value })
                }
              />
            </div>
            <div className="md:col-span-2">
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
                {saving
                  ? "Guardando…"
                  : editingId != null
                    ? "Guardar cambios"
                    : "Agregar"}
              </button>
            </div>
          </form>
        )}

        {holdings.isLoading ? (
          <LoadingSpinner />
        ) : tableRows.length === 0 ? (
          <div className="text-sm text-textMuted text-center py-6">
            Todavía no cargaste tenencias. Tocá "+ Agregar tenencia".
          </div>
        ) : (
          <div className="overflow-x-auto -mx-4">
            <table className="w-full text-sm">
              <thead className="bg-surfaceAlt text-textMuted text-xs uppercase">
                <tr>
                  <th
                    className="px-3 py-2 text-left cursor-pointer select-none hover:text-text"
                    onClick={() => toggleSort("symbol")}
                  >
                    Símbolo{sortIndicator("symbol")}
                  </th>
                  <th
                    className="px-3 py-2 text-right cursor-pointer select-none hover:text-text"
                    onClick={() => toggleSort("cantidad")}
                  >
                    Cantidad{sortIndicator("cantidad")}
                  </th>
                  <th
                    className="px-3 py-2 text-right cursor-pointer select-none hover:text-text"
                    onClick={() => toggleSort("price_usd")}
                  >
                    Precio{sortIndicator("price_usd")}
                  </th>
                  <th
                    className="px-3 py-2 text-right cursor-pointer select-none hover:text-text"
                    onClick={() => toggleSort("change_24h_pct")}
                  >
                    24h{sortIndicator("change_24h_pct")}
                  </th>
                  <th
                    className="px-3 py-2 text-right cursor-pointer select-none hover:text-text"
                    onClick={() => toggleSort("change_7d_pct")}
                  >
                    7d{sortIndicator("change_7d_pct")}
                  </th>
                  <th
                    className="px-3 py-2 text-right cursor-pointer select-none hover:text-text"
                    onClick={() => toggleSort("value_usd")}
                  >
                    Valor{sortIndicator("value_usd")}
                  </th>
                  <th
                    className="px-3 py-2 text-right cursor-pointer select-none hover:text-text"
                    onClick={() => toggleSort("costo_total_usd")}
                  >
                    Costo{sortIndicator("costo_total_usd")}
                  </th>
                  <th
                    className="px-3 py-2 text-right cursor-pointer select-none hover:text-text"
                    onClick={() => toggleSort("pnl_usd")}
                  >
                    P&L{sortIndicator("pnl_usd")}
                  </th>
                  <th
                    className="px-3 py-2 text-right cursor-pointer select-none hover:text-text"
                    onClick={() => toggleSort("pct_portfolio")}
                  >
                    % Cart.{sortIndicator("pct_portfolio")}
                  </th>
                  <th className="px-3 py-2 text-left">Exchange</th>
                  <th className="px-3 py-2 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {tableRows.map((it) => {
                  const price = currency === "USD" ? it.price_usd : it.price_ars;
                  const value = currency === "USD" ? it.value_usd : it.value_ars;
                  const cost =
                    it.costo_total_usd != null
                      ? currency === "USD"
                        ? it.costo_total_usd
                        : it.costo_total_usd * (r?.ars_rate || 0)
                      : null;
                  const pnl =
                    it.pnl_usd != null
                      ? currency === "USD"
                        ? it.pnl_usd
                        : it.pnl_usd * (r?.ars_rate || 0)
                      : null;
                  return (
                    <tr
                      key={it.id}
                      className="border-t border-border hover:bg-surfaceAlt/50"
                    >
                      <td className="px-3 py-2">
                        {cmcUrl(it.coingecko_id) ? (
                          <a
                            href={cmcUrl(it.coingecko_id)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium hover:text-accent hover:underline"
                          >
                            {it.symbol}
                          </a>
                        ) : (
                          <div className="font-medium">{it.symbol}</div>
                        )}
                        <div className="text-xs text-textMuted">
                          {it.name || "—"}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {formatNumber(it.cantidad)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {price != null ? fmt(price) : "—"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {it.change_24h_pct != null ? (
                          <span
                            className={
                              it.change_24h_pct >= 0
                                ? "text-success"
                                : "text-danger"
                            }
                          >
                            {it.change_24h_pct >= 0 ? "+" : ""}
                            {it.change_24h_pct.toFixed(2)}%
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {it.change_7d_pct != null ? (
                          <span
                            className={
                              it.change_7d_pct >= 0
                                ? "text-success"
                                : "text-danger"
                            }
                          >
                            {it.change_7d_pct >= 0 ? "+" : ""}
                            {it.change_7d_pct.toFixed(2)}%
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {value != null ? fmt(value) : "—"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {cost != null ? fmt(cost) : "—"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {pnl != null ? (
                          <span
                            className={pnl >= 0 ? "text-success" : "text-danger"}
                          >
                            {fmt(pnl)}
                            {it.pnl_pct != null && (
                              <div className="text-xs">
                                {it.pnl_pct >= 0 ? "+" : ""}
                                {it.pnl_pct.toFixed(2)}%
                              </div>
                            )}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {it.value_usd
                          ? `${it.pct_portfolio.toFixed(1)}%`
                          : "—"}
                      </td>
                      <td className="px-3 py-2 text-textMuted">
                        {it.exchange || "—"}
                      </td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">
                        <button
                          className="text-warn hover:underline mr-3 disabled:opacity-50"
                          disabled={!(it.cantidad > 0)}
                          onClick={() => setSellTarget(it)}
                        >
                          Vender
                        </button>
                        <button
                          className="text-accent hover:underline mr-3"
                          onClick={() =>
                            startEdit(
                              (holdings.data || []).find((h) => h.id === it.id) ||
                                it,
                            )
                          }
                        >
                          Editar
                        </button>
                        <button
                          className="text-danger hover:underline disabled:opacity-50"
                          disabled={deleteM.isPending}
                          onClick={() => {
                            if (confirm(`¿Eliminar ${it.symbol}?`))
                              deleteM.mutate(it.id);
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

      <SalesHistory
        sales={sales.data}
        loading={sales.isLoading}
        currency={currency}
        fmt={fmt}
        arsRate={r?.ars_rate}
        onDelete={(id) => deleteSaleM.mutate(id)}
        deleting={deleteSaleM.isPending}
      />

      {sellTarget && (
        <SellModal
          key={sellTarget.id}
          item={sellTarget}
          pending={sellM.isPending}
          error={
            sellM.isError
              ? sellM.error?.response?.data?.detail || "No se pudo registrar la venta."
              : null
          }
          onClose={() => {
            sellM.reset();
            setSellTarget(null);
          }}
          onConfirm={(payload) =>
            sellM.mutate({ id: sellTarget.id, payload })
          }
        />
      )}
    </div>
  );
}

function SalesHistory({ sales, loading, currency, fmt, arsRate, onDelete, deleting }) {
  if (loading) return null;
  const items = sales?.items || [];
  if (items.length === 0) return null;

  const conv = (usd) =>
    usd == null
      ? null
      : currency === "USD"
        ? usd
        : usd * (arsRate || 0);
  const totalPnl = conv(sales.total_pnl_usd);

  return (
    <div className="card p-4 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="label">Ventas realizadas</div>
        <div className="ml-auto text-sm">
          <span className="text-textMuted mr-2">P&L realizado:</span>
          <span
            className={`font-medium tabular-nums ${
              (sales.total_pnl_usd || 0) >= 0 ? "text-success" : "text-danger"
            }`}
          >
            {fmt(totalPnl || 0)}
            {sales.total_pnl_pct != null && (
              <> ({sales.total_pnl_pct >= 0 ? "+" : ""}
              {sales.total_pnl_pct.toFixed(2)}%)</>
            )}
          </span>
        </div>
      </div>
      <div className="overflow-x-auto -mx-4">
        <table className="w-full text-sm">
          <thead className="bg-surfaceAlt text-textMuted text-xs uppercase">
            <tr>
              <th className="px-3 py-2 text-left">Fecha</th>
              <th className="px-3 py-2 text-left">Símbolo</th>
              <th className="px-3 py-2 text-right">Cantidad</th>
              <th className="px-3 py-2 text-right">Precio venta</th>
              <th className="px-3 py-2 text-right">Ingreso</th>
              <th className="px-3 py-2 text-right">Costo</th>
              <th className="px-3 py-2 text-right">P&L</th>
              <th className="px-3 py-2 text-right">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => {
              const proceeds = conv(s.proceeds_usd);
              const cost = conv(s.cost_total_usd);
              const pnl = conv(s.pnl_usd);
              const price =
                currency === "USD"
                  ? s.price_usd
                  : s.price_usd * (arsRate || 0);
              return (
                <tr key={s.id} className="border-t border-border hover:bg-surfaceAlt/50">
                  <td className="px-3 py-2 text-textMuted whitespace-nowrap">
                    {formatDate(s.sold_at)}
                  </td>
                  <td className="px-3 py-2">
                    <div className="font-medium">{s.symbol}</div>
                    {s.notas && (
                      <div className="text-xs text-textMuted">{s.notas}</div>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatNumber(s.cantidad)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {price != null ? fmt(price) : "—"}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {proceeds != null ? fmt(proceeds) : "—"}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {cost != null ? fmt(cost) : "—"}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {pnl != null ? (
                      <span className={pnl >= 0 ? "text-success" : "text-danger"}>
                        {fmt(pnl)}
                        {s.pnl_pct != null && (
                          <div className="text-xs">
                            {s.pnl_pct >= 0 ? "+" : ""}
                            {s.pnl_pct.toFixed(2)}%
                          </div>
                        )}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      className="text-danger hover:underline disabled:opacity-50"
                      disabled={deleting}
                      onClick={() => {
                        if (confirm(`¿Borrar este registro de venta de ${s.symbol}? No restaura la tenencia.`))
                          onDelete(s.id);
                      }}
                    >
                      Borrar
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
