import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getHoldings, getKpis } from "../api/portfolio";
import { operationsSummary } from "../api/operations";
import { listSnapshots } from "../api/snapshots";
import { getCryptoReport, listCryptoSnapshots } from "../api/crypto";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import AssetDonutChart from "../components/charts/AssetDonutChart.jsx";
import OperationsBarChart from "../components/charts/OperationsBarChart.jsx";
import PortfolioLineChart from "../components/charts/PortfolioLineChart.jsx";
import { formatARS, formatPct, formatUSD } from "../utils/format";
import { useUiStore } from "../store/uiStore";
import { periodToDays, periodToDates } from "../utils/periods";

function SectionTitle({ children }) {
  return (
    <div className="text-xs uppercase tracking-wider text-textMuted font-semibold pt-2 pb-1 border-b border-border">
      {children}
    </div>
  );
}

export default function AnalisisScreen() {
  const currency = useUiStore((s) => s.currency);
  const fmt = currency === "USD" ? formatUSD : formatARS;
  const [selectedClass, setSelectedClass] = useState(null);
  const [snapPeriod, setSnapPeriod] = useState("MAX");
  const [opsPeriod, setOpsPeriod] = useState("YTD");
  const snapDays = periodToDays(snapPeriod);
  const { fromDate: opsFrom, toDate: opsTo } = periodToDates(opsPeriod);

  const kpis     = useQuery({ queryKey: ["kpis"], queryFn: getKpis });
  const holdings = useQuery({ queryKey: ["holdings"], queryFn: () => getHoldings(false) });
  const snaps    = useQuery({ queryKey: ["snapshots", snapDays], queryFn: () => listSnapshots(snapDays) });
  const sum      = useQuery({ queryKey: ["opsSummary", opsFrom, opsTo], queryFn: () => operationsSummary({ fromDate: opsFrom, toDate: opsTo }) });
  const cryptoR  = useQuery({ queryKey: ["crypto-report"], queryFn: getCryptoReport, staleTime: 60_000 });
  const cryptoSn = useQuery({ queryKey: ["crypto-snapshots", 365], queryFn: () => listCryptoSnapshots(365) });

  // --- IOL performers ---
  const performers = useMemo(() => {
    const list = (holdings.data || []).slice();
    list.sort((a, b) => Number(b.ganancia_porcentaje || 0) - Number(a.ganancia_porcentaje || 0));
    return { top: list.slice(0, 5), worst: list.slice(-5).reverse() };
  }, [holdings.data]);

  // --- IOL operations bar chart ---
  const opsByBucket = useMemo(() => {
    return (sum.data?.by_simbolo || []).map((s) => ({
      simbolo: s.simbolo,
      pnl_ars: Number(s.ventas_ars || 0) - Number(s.compras_ars || 0),
      pnl_usd: Number(s.ventas_usd || 0) - Number(s.compras_usd || 0),
    }));
  }, [sum.data]);

  // --- Crypto distribution (for donut) ---
  const cryptoDist = useMemo(() => {
    const rate = cryptoR.data?.ars_rate || 0;
    return (cryptoR.data?.items || [])
      .filter((i) => i.value_usd && i.value_usd > 0)
      .map((i) => ({
        clase:     i.symbol,
        valor_usd: i.value_usd || 0,
        valor_ars: i.value_ars || (i.value_usd * rate) || 0,
        pct:       i.pct_portfolio || 0,
      }));
  }, [cryptoR.data]);

  // --- Crypto performers ---
  const cryptoPerformers = useMemo(() => {
    const list = (cryptoR.data?.items || [])
      .filter((i) => i.pnl_pct != null)
      .slice()
      .sort((a, b) => Number(b.pnl_pct || 0) - Number(a.pnl_pct || 0));
    return { top: list.slice(0, 5), worst: list.slice(-5).reverse() };
  }, [cryptoR.data]);

  // --- Combined totals ---
  const iolTotalArs = kpis.data?.total_ars || 0;
  const iolTotalUsd = kpis.data?.total_usd || 0;
  const cryptoTotalArs = cryptoR.data?.total_value_ars || 0;
  const cryptoTotalUsd = cryptoR.data?.total_value_usd || 0;
  const totalArs = iolTotalArs + cryptoTotalArs;
  const totalUsd = iolTotalUsd + cryptoTotalUsd;

  if (kpis.isLoading || holdings.isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Análisis</h1>

      {/* ── TOTALES COMBINADOS ────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-3">
        <div className="card p-4">
          <div className="label mb-1">IOL</div>
          <div className="text-xl font-semibold tabular-nums">
            {currency === "USD" ? formatUSD(iolTotalUsd) : formatARS(iolTotalArs)}
          </div>
        </div>
        <div className="card p-4">
          <div className="label mb-1">Crypto</div>
          <div className="text-xl font-semibold tabular-nums">
            {currency === "USD" ? formatUSD(cryptoTotalUsd) : formatARS(cryptoTotalArs)}
          </div>
        </div>
        <div className="card p-4 border-accent/30">
          <div className="label mb-1">Cartera total</div>
          <div className="text-xl font-semibold tabular-nums text-accent">
            {currency === "USD" ? formatUSD(totalUsd) : formatARS(totalArs)}
          </div>
        </div>
      </div>

      {/* ── DISTRIBUCIÓN ─────────────────────────────────────────── */}
      <SectionTitle>Distribución</SectionTitle>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <AssetDonutChart
          data={kpis.data?.distribucion_por_clase || []}
          selectedClass={selectedClass}
          onSelect={setSelectedClass}
          title="Por clase (IOL)"
        />
        {cryptoDist.length > 0 ? (
          <AssetDonutChart
            data={cryptoDist}
            title="Por moneda (Crypto)"
          />
        ) : (
          <div className="card p-4 flex items-center justify-center text-sm text-textMuted">
            Sin datos de crypto con precio en vivo.
          </div>
        )}
      </div>

      {/* ── OPERACIONES IOL ───────────────────────────────────────── */}
      <SectionTitle>Operaciones IOL 2026</SectionTitle>
      <OperationsBarChart
        data={opsByBucket}
        title="Resultado neto por símbolo (Ventas − Compras)"
        period={opsPeriod}
        onPeriodChange={setOpsPeriod}
      />

      {/* ── EVOLUCIÓN ────────────────────────────────────────────── */}
      <SectionTitle>Evolución IOL</SectionTitle>
      <PortfolioLineChart
        data={snaps.data || []}
        selectedClass={selectedClass}
        period={snapPeriod}
        onPeriodChange={setSnapPeriod}
      />

      <SectionTitle>Evolución Crypto</SectionTitle>
      <PortfolioLineChart data={cryptoSn.data || []} />

      {/* ── PERFORMERS ───────────────────────────────────────────── */}
      <SectionTitle>Performers IOL</SectionTitle>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-4">
          <div className="label mb-3">Top performers</div>
          <ul className="divide-y divide-border">
            {performers.top.map((h) => (
              <li key={h.id} className="py-2 flex justify-between">
                <div>
                  <div className="font-medium">{h.simbolo}</div>
                  <div className="text-xs text-textMuted">{h.clase}</div>
                </div>
                <div className="text-right tabular-nums">
                  <div>{fmt(currency === "USD" ? h.valuacion_usd : h.valuacion_ars)}</div>
                  <div className="text-xs text-success">{formatPct(h.ganancia_porcentaje)}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="card p-4">
          <div className="label mb-3">Worst performers</div>
          <ul className="divide-y divide-border">
            {performers.worst.map((h) => (
              <li key={h.id} className="py-2 flex justify-between">
                <div>
                  <div className="font-medium">{h.simbolo}</div>
                  <div className="text-xs text-textMuted">{h.clase}</div>
                </div>
                <div className="text-right tabular-nums">
                  <div>{fmt(currency === "USD" ? h.valuacion_usd : h.valuacion_ars)}</div>
                  <div className="text-xs text-danger">{formatPct(h.ganancia_porcentaje)}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <SectionTitle>Performers Crypto</SectionTitle>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-4">
          <div className="label mb-3">Top performers</div>
          {cryptoPerformers.top.length === 0 ? (
            <div className="text-sm text-textMuted">Sin datos de P&L crypto.</div>
          ) : (
            <ul className="divide-y divide-border">
              {cryptoPerformers.top.map((i) => (
                <li key={i.id} className="py-2 flex justify-between">
                  <div>
                    <div className="font-medium">{i.symbol}</div>
                    <div className="text-xs text-textMuted">{i.name || i.coingecko_id || "—"}</div>
                  </div>
                  <div className="text-right tabular-nums">
                    <div>{fmt(currency === "USD" ? i.value_usd : i.value_ars)}</div>
                    <div className="text-xs text-success">
                      {i.pnl_pct >= 0 ? "+" : ""}{i.pnl_pct.toFixed(2)}%
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="card p-4">
          <div className="label mb-3">Worst performers</div>
          {cryptoPerformers.worst.length === 0 ? (
            <div className="text-sm text-textMuted">Sin datos de P&L crypto.</div>
          ) : (
            <ul className="divide-y divide-border">
              {cryptoPerformers.worst.map((i) => (
                <li key={i.id} className="py-2 flex justify-between">
                  <div>
                    <div className="font-medium">{i.symbol}</div>
                    <div className="text-xs text-textMuted">{i.name || i.coingecko_id || "—"}</div>
                  </div>
                  <div className="text-right tabular-nums">
                    <div>{fmt(currency === "USD" ? i.value_usd : i.value_ars)}</div>
                    <div className="text-xs text-danger">
                      {i.pnl_pct >= 0 ? "+" : ""}{i.pnl_pct.toFixed(2)}%
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
