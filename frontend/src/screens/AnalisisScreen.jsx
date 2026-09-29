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

// Top: mayores ganancias (> 0). Worst: mayores pérdidas (< 0). Así una lista corta
// no muestra el mismo activo en ambas, ni un ganador en "Worst".
function splitPerformers(list, pct) {
  const top = list.filter((x) => pct(x) > 0).sort((a, b) => pct(b) - pct(a)).slice(0, 5);
  const worst = list.filter((x) => pct(x) < 0).sort((a, b) => pct(a) - pct(b)).slice(0, 5);
  return { top, worst };
}

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
  const [cryptoSnapPeriod, setCryptoSnapPeriod] = useState("MAX");
  const snapDays = periodToDays(snapPeriod);
  const cryptoSnapDays = periodToDays(cryptoSnapPeriod);
  const { fromDate: opsFrom, toDate: opsTo } = periodToDates(opsPeriod);

  const kpis     = useQuery({ queryKey: ["kpis"], queryFn: getKpis });
  const holdings = useQuery({ queryKey: ["holdings"], queryFn: () => getHoldings(false) });
  const snaps    = useQuery({ queryKey: ["snapshots", snapDays], queryFn: () => listSnapshots(snapDays) });
  const sum      = useQuery({ queryKey: ["opsSummary", opsFrom, opsTo], queryFn: () => operationsSummary({ fromDate: opsFrom, toDate: opsTo }) });
  const cryptoR  = useQuery({ queryKey: ["crypto-report"], queryFn: getCryptoReport, staleTime: 60_000 });
  const cryptoSn = useQuery({ queryKey: ["crypto-snapshots", cryptoSnapDays], queryFn: () => listCryptoSnapshots(cryptoSnapDays) });

  // --- IOL performers (top sólo positivos, worst sólo negativos, sin solaparse) ---
  const performers = useMemo(
    () => splitPerformers(holdings.data || [], (h) => Number(h.ganancia_porcentaje || 0)),
    [holdings.data]
  );

  // --- IOL: lo cobrado por símbolo (renta + dividendos + amortizaciones) ---
  const opsByBucket = useMemo(() => {
    const cobrado = (s, cur) =>
      Number(s[`renta_${cur}`] || 0) + Number(s[`dividendos_${cur}`] || 0) + Number(s[`amortizaciones_${cur}`] || 0);
    return (sum.data?.by_simbolo || []).map((s) => ({
      simbolo: s.simbolo,
      pnl_ars: cobrado(s, "ars"),
      pnl_usd: cobrado(s, "usd"),
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
  const cryptoPerformers = useMemo(
    () => splitPerformers((cryptoR.data?.items || []).filter((i) => i.pnl_pct != null), (i) => Number(i.pnl_pct)),
    [cryptoR.data]
  );

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
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
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
      <SectionTitle>Operaciones IOL</SectionTitle>
      <OperationsBarChart
        data={opsByBucket}
        title="Cobrado por símbolo (renta + dividendos + amortizaciones)"
        valueLabel="Cobrado"
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
      <PortfolioLineChart
        data={cryptoSn.data || []}
        period={cryptoSnapPeriod}
        onPeriodChange={setCryptoSnapPeriod}
        title="Evolución Crypto"
      />

      {/* ── PERFORMERS ───────────────────────────────────────────── */}
      <SectionTitle>Performers IOL</SectionTitle>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-4">
          <div className="label mb-3">Top performers</div>
          {performers.top.length === 0 && <div className="text-sm text-textMuted">Ninguna tenencia en ganancia.</div>}
          <ul className="divide-y divide-border">
            {performers.top.map((h) => (
              <li key={h.id} className="py-2 flex justify-between">
                <div>
                  <div className="font-medium">{h.simbolo}</div>
                  <div className="text-xs text-textMuted">{h.clase}</div>
                </div>
                <div className="text-right tabular-nums">
                  <div>{fmt(currency === "USD" ? h.valuacion_usd : h.valuacion_ars)}</div>
                  <div className="text-xs text-success">+{formatPct(h.ganancia_porcentaje)}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="card p-4">
          <div className="label mb-3">Worst performers</div>
          {performers.worst.length === 0 && <div className="text-sm text-textMuted">Ninguna tenencia en pérdida.</div>}
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
