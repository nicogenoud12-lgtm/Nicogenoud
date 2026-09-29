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
import Card from "../components/Card.jsx";
import Delta from "../components/Delta.jsx";
import KpiCard from "../components/KpiCard.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import PageHeader from "../components/PageHeader.jsx";
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

// ---- Presentación ----------------------------------------------------------

const iconProps = {
  width: 16,
  height: 16,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
  className: "shrink-0",
};

const IconRefresh = () => (
  <svg {...iconProps}>
    <path d="M21 12a9 9 0 1 1-2.64-6.36" />
    <path d="M21 3v6h-6" />
  </svg>
);
const IconPlus = () => (
  <svg {...iconProps}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);
const IconClose = () => (
  <svg {...iconProps}>
    <path d="M18 6 6 18M6 6l12 12" />
  </svg>
);
const IconInfo = () => (
  <svg {...iconProps} className="shrink-0 mt-0.5">
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5M12 8h.01" />
  </svg>
);
const IconAlert = () => (
  <svg {...iconProps} className="shrink-0 mt-0.5">
    <path d="M12 3 2.5 20h19L12 3Z" />
    <path d="M12 10v4M12 17h.01" />
  </svg>
);
const IconCheck = () => (
  <svg {...iconProps} className="shrink-0 mt-0.5">
    <path d="m5 12 5 5 9-10" />
  </svg>
);

// Monto con signo explícito: el color acompaña al signo, nunca va solo.
function signedMoney(fmt, n) {
  if (n == null || !isFinite(Number(n))) return "—";
  const v = Number(n);
  const abs = fmt(Math.abs(v));
  return v > 0 ? `+${abs}` : v < 0 ? `−${abs}` : abs;
}
function toneClass(n) {
  const v = Number(n || 0);
  return v > 0 ? "text-success" : v < 0 ? "text-danger" : "text-textMuted";
}
function toneOf(n) {
  const v = Number(n || 0);
  return v > 0 ? "positive" : v < 0 ? "negative" : "neutral";
}

// Estilo de tabla alineado con DataTable (bordes hairline, cifras tabulares).
const TH =
  "px-4 h-10 text-left text-xs font-medium text-textMuted whitespace-nowrap first:pl-5 last:pr-5";
const TD = "px-4 h-11 py-2 whitespace-nowrap first:pl-5 last:pr-5";
const TD_NUM = `${TD} text-right num`;
const TR =
  "border-b border-border last:border-b-0 hover:bg-surfaceAlt/60 transition-colors";
const ROW_ACTION_BASE =
  "text-[13px] text-textMuted transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
const ROW_ACTION = `${ROW_ACTION_BASE} hover:text-text`;
const ROW_ACTION_DANGER = `${ROW_ACTION_BASE} hover:text-danger`;

// ---------------------------------------------------------------------------

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
        <div className="absolute z-20 mt-1 w-full card py-1 max-h-72 overflow-y-auto">
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
              className="w-full text-left px-3 h-9 hover:bg-surfaceAlt flex items-center gap-2.5 text-[13px] transition-colors"
            >
              {c.thumb && (
                <img src={c.thumb} alt="" className="h-4 w-4 rounded-full" />
              )}
              <span className="font-medium text-text">{c.symbol}</span>
              <span className="text-textMuted truncate">{c.name}</span>
              {c.market_cap_rank && (
                <span className="ml-auto text-xs text-textMuted num">
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="card card-pad w-full max-w-md">
        <div className="flex items-start justify-between gap-3 mb-5">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-text">Vender {item.symbol}</h2>
            <div className="text-xs text-textMuted mt-0.5">
              Tenencia actual: <span className="num">{formatNumber(held)}</span>
            </div>
          </div>
          <button
            className="btn-ghost h-8 w-8 px-0"
            onClick={onClose}
            type="button"
            aria-label="Cerrar"
          >
            <IconClose />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <span className="label">Cantidad a vender</span>
              <button
                type="button"
                className="text-xs text-textMuted hover:text-text underline-offset-2 hover:underline num"
                onClick={() => setQty(String(held))}
              >
                Máx: {formatNumber(held)}
              </button>
            </div>
            <input
              className="input num"
              type="number"
              step="any"
              min="0"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              required
            />
            {qtyN != null && qtyN > held + 1e-9 && (
              <div className="text-xs text-danger mt-1.5">
                Supera tu tenencia ({formatNumber(held)}).
              </div>
            )}
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <span className="label">Precio de venta (USD por unidad)</span>
              {livePrice != null && (
                <button
                  type="button"
                  className="text-xs text-textMuted hover:text-text underline-offset-2 hover:underline num"
                  onClick={() => setPrice(String(livePrice))}
                >
                  En vivo: {formatUSD(livePrice)}
                </button>
              )}
            </div>
            <input
              className="input num"
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
            <div className="label mb-1.5">Notas</div>
            <input
              className="input"
              placeholder="Opcional"
              value={notas}
              onChange={(e) => setNotas(e.target.value)}
            />
          </div>

          <div className="rounded-lg border border-border px-3 text-[13px] divide-hair">
            <div className="flex justify-between gap-3 py-2">
              <span className="text-textMuted">Ingreso por venta</span>
              <span className="num text-text">
                {proceeds != null ? formatUSD(proceeds) : "—"}
              </span>
            </div>
            <div className="flex justify-between gap-3 py-2">
              <span className="text-textMuted">Costo (promedio)</span>
              <span className="num text-text">
                {costTotal != null ? formatUSD(costTotal) : "—"}
              </span>
            </div>
            <div className="flex justify-between gap-3 py-2 font-medium">
              <span className="text-textSecondary">P&L realizado</span>
              <span className="num text-right">
                <span className={pnl == null ? "text-textMuted" : toneClass(pnl)}>
                  {signedMoney(formatUSD, pnl)}
                </span>
                {pnlPct != null && (
                  <span className="ml-2 font-normal">
                    <Delta value={pnlPct} />
                  </span>
                )}
              </span>
            </div>
            {qtyN != null && qtyN < held - 1e-9 && (
              <div className="py-2 text-xs text-textMuted">
                Quedan <span className="num">{formatNumber(held - qtyN)}</span> {item.symbol} en cartera.
              </div>
            )}
          </div>

          {error && <div className="text-[13px] text-danger">{error}</div>}

          <div className="flex gap-2 justify-end pt-1">
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
  const sortTh = (key, label, align = "right") => (
    <th
      key={key}
      className={`${TH} cursor-pointer select-none hover:text-text ${
        align === "right" ? "text-right" : ""
      }`}
      onClick={() => toggleSort(key)}
      aria-sort={
        sortKey === key ? (sortDir === "asc" ? "ascending" : "descending") : undefined
      }
    >
      {label}
      {sortKey === key && (
        <span className="ml-1 text-text">{sortDir === "desc" ? "↓" : "↑"}</span>
      )}
    </th>
  );

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

  const subtitle = report.isFetching
    ? "Actualizando cotizaciones…"
    : r?.fetched_at
      ? `Cotizaciones de las ${new Date(r.fetched_at).toLocaleTimeString("es-AR")}`
      : "Tenencias propias con cotización en vivo";

  return (
    <div>
      <PageHeader
        title="Crypto"
        subtitle={subtitle}
        actions={
          <button
            className="btn-secondary"
            onClick={() => backfillM.mutate()}
            disabled={backfillM.isPending}
            title="Completa los días sin snapshot desde el 1° de enero con precios históricos. Reconstruye las cantidades sumando lo vendido después de cada día. No pisa los días ya guardados."
          >
            <IconRefresh />
            {backfillM.isPending ? "Recalculando…" : "Recalcular evolución"}
          </button>
        }
      />

      <div className="space-y-6">
        {(backfillM.isSuccess && backfillM.data) ||
        r?.fetch_error ||
        r?.missing_coingecko?.length > 0 ? (
          <div className="space-y-2">
            {backfillM.isSuccess && backfillM.data && (
              <div className="notice">
                <IconCheck />
                <div>
                  Evolución completada: {backfillM.data.days} días nuevos desde{" "}
                  {backfillM.data.since}
                  {backfillM.data.skipped_existing > 0 && (
                    <> · {backfillM.data.skipped_existing} ya existían (no se tocaron)</>
                  )}
                  {backfillM.data.skipped_incomplete > 0 && (
                    <> · {backfillM.data.skipped_incomplete} sin precio completo</>
                  )}
                  {backfillM.data.failed_symbols?.length > 0 && (
                    <> · Sin historial: {backfillM.data.failed_symbols.join(", ")}</>
                  )}
                </div>
              </div>
            )}

            {r?.fetch_error && (
              <div className="notice">
                <IconAlert />
                <div>
                  <span className="font-medium text-text">Atención:</span> No se
                  pudieron obtener cotizaciones: {r.fetch_error}. Se muestran los
                  datos por costo cargado.
                </div>
              </div>
            )}
            {r?.missing_coingecko?.length > 0 && (
              <div className="notice">
                <IconInfo />
                <div>
                  Sin precio en vivo:{" "}
                  <span className="font-medium text-text">
                    {r.missing_coingecko.join(", ")}
                  </span>
                  . Editá la tenencia y elegí la moneda desde el buscador para
                  asignarle un ID de CoinGecko.
                </div>
              </div>
            )}
          </div>
        ) : null}

        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="col-span-2 lg:col-span-1 min-w-0 [&>*]:h-full">
            <KpiCard
              hero
              label={`Valor total (${currency})`}
              value={<span className="num">{fmt(totalValue || 0)}</span>}
              sub={
                r?.ars_rate
                  ? `Dólar ${r.dolar_source}: ${formatARS(Number(r.ars_rate))}`
                  : null
              }
            />
          </div>
          <KpiCard
            label={`Costo (${currency})`}
            value={<span className="num">{fmt(totalCost || 0)}</span>}
          />
          <KpiCard
            label="P&L"
            value={<span className="num">{signedMoney(fmt, pnlValue || 0)}</span>}
            tone={toneOf(pnlValue)}
            sub={r?.pnl_total_pct != null ? <Delta value={r.pnl_total_pct} /> : null}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 min-w-0">
            <PortfolioLineChart
              data={snaps.data || []}
              period={snapPeriod}
              onPeriodChange={setSnapPeriod}
              title="Evolución crypto"
              className="h-[22rem]"
            />
          </div>
          {distribution.length > 0 ? (
            <AssetDonutChart
              data={distribution}
              title="Distribución por moneda"
            />
          ) : (
            <div className="card card-pad flex items-center justify-center text-center text-sm text-textMuted">
              Cargá tenencias con precio en vivo para ver la distribución.
            </div>
          )}
        </div>

        <Card title="Mayores movimientos" subtitle="Variación de las últimas 24 h">
          {movers.length === 0 ? (
            <div className="text-sm text-textMuted">
              Sin datos de variación. Asegurate de que tus tenencias tengan asignado
              un ID de CoinGecko.
            </div>
          ) : (
            <ul className="divide-hair -my-2">
              {movers.map((m) => (
                <li
                  key={m.id}
                  className="py-2.5 flex items-center justify-between gap-3 text-[13px]"
                >
                  <div className="min-w-0">
                    <div className="font-medium text-text">{m.symbol}</div>
                    <div className="text-xs text-textMuted truncate">
                      {m.name || m.coingecko_id}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="num text-text">
                      {fmt(currency === "USD" ? m.value_usd : m.value_ars)}
                    </div>
                    <Delta value={m.change_24h_pct} className="text-xs" />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <section className="card min-w-0">
          <div className="flex items-start justify-between gap-3 p-5 pb-4">
            <div className="min-w-0">
              <h2 className="section-title">Mis tenencias</h2>
              <div className="text-xs text-textMuted mt-0.5">
                {tableRows.length > 0
                  ? `${tableRows.length} ${tableRows.length === 1 ? "moneda" : "monedas"} · ${currency}`
                  : "Cargadas a mano, cotizadas con CoinGecko"}
              </div>
            </div>
            <button
              className={showForm ? "btn-secondary" : "btn-primary"}
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
              {showForm && editingId == null ? (
                "Cerrar"
              ) : (
                <>
                  <IconPlus />
                  Agregar tenencia
                </>
              )}
            </button>
          </div>

          {showForm && (
            <form
              onSubmit={handleSubmit}
              className="grid grid-cols-1 md:grid-cols-6 gap-4 border-t border-border p-5"
            >
              <div className="md:col-span-6 section-title">
                {editingId != null ? "Editar tenencia" : "Nueva tenencia"}
              </div>
              <div className="md:col-span-3">
                <div className="label mb-1.5">Buscar en CoinGecko</div>
                <CoinPicker onPick={handlePick} />
                {form.coingecko_id && (
                  <div className="text-xs text-textMuted mt-1.5">
                    ID: <code className="font-mono text-textSecondary">{form.coingecko_id}</code>
                  </div>
                )}
              </div>
              <div className="md:col-span-1">
                <div className="label mb-1.5">Símbolo *</div>
                <input
                  className="input uppercase"
                  placeholder="BTC"
                  value={form.symbol}
                  onChange={(e) => setForm({ ...form, symbol: e.target.value })}
                  required
                />
              </div>
              <div className="md:col-span-2">
                <div className="label mb-1.5">Nombre</div>
                <input
                  className="input"
                  placeholder="Bitcoin"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </div>
              <div className="md:col-span-2">
                <div className="label mb-1.5">Cantidad *</div>
                <input
                  className="input num"
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
                <div className="label mb-1.5">Costo unitario (USD)</div>
                <input
                  className="input num"
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
                <div className="label mb-1.5">Exchange o wallet</div>
                <input
                  className="input"
                  placeholder="Binance"
                  value={form.exchange}
                  onChange={(e) => setForm({ ...form, exchange: e.target.value })}
                />
              </div>
              <div className="md:col-span-6">
                <div className="label mb-1.5">Notas</div>
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
            <div className="border-t border-border px-5">
              <LoadingSpinner />
            </div>
          ) : tableRows.length === 0 ? (
            <div className="border-t border-border px-5 py-12 text-center text-sm text-textMuted">
              Todavía no cargaste tenencias. Tocá "Agregar tenencia".
            </div>
          ) : (
            <div className="overflow-x-auto border-t border-border">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-border">
                    {sortTh("symbol", "Símbolo", "left")}
                    {sortTh("cantidad", "Cantidad")}
                    {sortTh("price_usd", "Precio")}
                    {sortTh("change_24h_pct", "24 h")}
                    {sortTh("change_7d_pct", "7 d")}
                    {sortTh("value_usd", "Valor")}
                    {sortTh("costo_total_usd", "Costo")}
                    {sortTh("pnl_usd", "P&L")}
                    {sortTh("pct_portfolio", "% cartera")}
                    <th className={TH}>Exchange</th>
                    <th className={`${TH} text-right`}>
                      <span className="sr-only">Acciones</span>
                    </th>
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
                      <tr key={it.id} className={TR}>
                        <td className={TD}>
                          {cmcUrl(it.coingecko_id) ? (
                            <a
                              href={cmcUrl(it.coingecko_id)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="font-medium text-text underline-offset-2 hover:underline"
                              title="Ver en CoinMarketCap"
                            >
                              {it.symbol}
                            </a>
                          ) : (
                            <div className="font-medium text-text">{it.symbol}</div>
                          )}
                          <div className="text-xs text-textMuted">
                            {it.name || "—"}
                          </div>
                        </td>
                        <td className={TD_NUM}>{formatNumber(it.cantidad)}</td>
                        <td className={TD_NUM}>{price != null ? fmt(price) : "—"}</td>
                        <td className={TD_NUM}>
                          <Delta value={it.change_24h_pct} />
                        </td>
                        <td className={TD_NUM}>
                          <Delta value={it.change_7d_pct} />
                        </td>
                        <td className={`${TD_NUM} text-text`}>
                          {value != null ? fmt(value) : "—"}
                        </td>
                        <td className={TD_NUM}>{cost != null ? fmt(cost) : "—"}</td>
                        <td className={TD_NUM}>
                          {pnl != null ? (
                            <>
                              <div className={toneClass(pnl)}>{signedMoney(fmt, pnl)}</div>
                              {it.pnl_pct != null && (
                                <Delta value={it.pnl_pct} className="text-xs" />
                              )}
                            </>
                          ) : (
                            <span className="text-textMuted">—</span>
                          )}
                        </td>
                        <td className={`${TD_NUM} text-textSecondary`}>
                          {it.value_usd
                            ? `${it.pct_portfolio.toFixed(1).replace(".", ",")}%`
                            : "—"}
                        </td>
                        <td className={`${TD} text-textMuted`}>
                          {it.exchange || "—"}
                        </td>
                        <td className={`${TD} text-right`}>
                          <div className="inline-flex items-center gap-3">
                            <button
                              className={ROW_ACTION}
                              disabled={!(it.cantidad > 0)}
                              onClick={() => setSellTarget(it)}
                            >
                              Vender
                            </button>
                            <button
                              className={ROW_ACTION}
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
                              className={ROW_ACTION_DANGER}
                              disabled={deleteM.isPending}
                              onClick={() => {
                                if (confirm(`¿Eliminar ${it.symbol}?`))
                                  deleteM.mutate(it.id);
                              }}
                            >
                              Eliminar
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <SalesHistory
          sales={sales.data}
          loading={sales.isLoading}
          currency={currency}
          fmt={fmt}
          arsRate={r?.ars_rate}
          onDelete={(id) => deleteSaleM.mutate(id)}
          deleting={deleteSaleM.isPending}
        />
      </div>

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

  // Cada venta se pasa a ARS con la cotización del día de esa venta; la
  // actual sólo se usa si la venta no tiene una guardada.
  const conv = (usd, rate) =>
    usd == null
      ? null
      : currency === "USD"
        ? usd
        : usd * (rate || arsRate || 0);
  const totalPnl =
    currency === "USD" ? sales.total_pnl_usd : sales.total_pnl_ars;

  return (
    <section className="card min-w-0">
      <div className="flex flex-wrap items-start justify-between gap-3 p-5 pb-4">
        <div className="min-w-0">
          <h2 className="section-title">Ventas realizadas</h2>
          <div className="text-xs text-textMuted mt-0.5">
            Convertidas con la cotización del día de cada venta
          </div>
        </div>
        <div className="text-right">
          <div className="label">P&L realizado</div>
          <div className="mt-0.5 text-sm font-medium num">
            <span className={toneClass(totalPnl)}>{signedMoney(fmt, totalPnl || 0)}</span>
            {sales.total_pnl_pct != null && (
              <span className="ml-2 font-normal">
                <Delta value={sales.total_pnl_pct} />
              </span>
            )}
          </div>
        </div>
      </div>
      <div className="overflow-x-auto border-t border-border">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-border">
              <th className={TH}>Fecha</th>
              <th className={TH}>Símbolo</th>
              <th className={`${TH} text-right`}>Cantidad</th>
              <th className={`${TH} text-right`}>Precio de venta</th>
              <th className={`${TH} text-right`}>Ingreso</th>
              <th className={`${TH} text-right`}>Costo</th>
              <th className={`${TH} text-right`}>P&L</th>
              <th className={`${TH} text-right`}>
                <span className="sr-only">Acciones</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => {
              const proceeds = conv(s.proceeds_usd, s.dolar_rate);
              const cost = conv(s.cost_total_usd, s.dolar_rate);
              const pnl = conv(s.pnl_usd, s.dolar_rate);
              const price = conv(s.price_usd, s.dolar_rate);
              return (
                <tr key={s.id} className={TR}>
                  <td className={`${TD} text-textMuted`}>{formatDate(s.sold_at)}</td>
                  <td className={TD}>
                    <div className="font-medium text-text">{s.symbol}</div>
                    {s.notas && (
                      <div className="text-xs text-textMuted">{s.notas}</div>
                    )}
                  </td>
                  <td className={TD_NUM}>{formatNumber(s.cantidad)}</td>
                  <td className={TD_NUM}>{price != null ? fmt(price) : "—"}</td>
                  <td className={TD_NUM}>{proceeds != null ? fmt(proceeds) : "—"}</td>
                  <td className={TD_NUM}>{cost != null ? fmt(cost) : "—"}</td>
                  <td className={TD_NUM}>
                    {pnl != null ? (
                      <>
                        <div className={toneClass(pnl)}>{signedMoney(fmt, pnl)}</div>
                        {s.pnl_pct != null && (
                          <Delta value={s.pnl_pct} className="text-xs" />
                        )}
                      </>
                    ) : (
                      <span className="text-textMuted">—</span>
                    )}
                  </td>
                  <td className={`${TD} text-right`}>
                    <button
                      className={ROW_ACTION_DANGER}
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
    </section>
  );
}
