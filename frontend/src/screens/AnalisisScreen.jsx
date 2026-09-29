import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getHoldings, getKpis } from "../api/portfolio";
import { operationsSummary } from "../api/operations";
import { listSnapshots } from "../api/snapshots";
import { getCryptoReport, listCryptoSnapshots } from "../api/crypto";
import Card from "../components/Card.jsx";
import Delta from "../components/Delta.jsx";
import KpiCard from "../components/KpiCard.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import PageHeader from "../components/PageHeader.jsx";
import AssetDonutChart from "../components/charts/AssetDonutChart.jsx";
import OperationsBarChart from "../components/charts/OperationsBarChart.jsx";
import PortfolioLineChart from "../components/charts/PortfolioLineChart.jsx";
import { formatARS, formatUSD } from "../utils/format";
import { useUiStore } from "../store/uiStore";
import { periodToDays, periodToDates } from "../utils/periods";

// Top: mayores ganancias (> 0). Worst: mayores pérdidas (< 0). Así una lista corta
// no muestra el mismo activo en ambas, ni un ganador en "Worst".
function splitPerformers(list, pct) {
  const top = list.filter((x) => pct(x) > 0).sort((a, b) => pct(b) - pct(a)).slice(0, 5);
  const worst = list.filter((x) => pct(x) < 0).sort((a, b) => pct(a) - pct(b)).slice(0, 5);
  return { top, worst };
}

function PerformerList({ items, empty, render }) {
  if (!items.length) return <div className="text-sm text-textMuted py-1">{empty}</div>;
  return <ul className="divide-hair -my-2.5">{items.map(render)}</ul>;
}

function PerformerRow({ id, name, detail, value, pct }) {
  return (
    <li key={id} className="flex items-center justify-between gap-3 py-2.5">
      <div className="min-w-0">
        <div className="text-sm font-medium text-text truncate">{name}</div>
        <div className="text-xs text-textMuted truncate">{detail}</div>
      </div>
      <div className="text-right shrink-0">
        <div className="text-sm text-text num">{value}</div>
        <div className="text-xs">
          <Delta value={pct} />
        </div>
      </div>
    </li>
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

  const total = currency === "USD" ? totalUsd : totalArs;
  const share = (part) => (total > 0 ? `${((part / total) * 100).toFixed(1).replace(".", ",")}% del total` : "—");
  const iolShown = currency === "USD" ? iolTotalUsd : iolTotalArs;
  const cryptoShown = currency === "USD" ? cryptoTotalUsd : cryptoTotalArs;

  const holdingRow = (h) => (
    <PerformerRow
      key={h.id}
      id={h.id}
      name={h.simbolo}
      detail={h.clase}
      value={fmt(currency === "USD" ? h.valuacion_usd : h.valuacion_ars)}
      pct={Number(h.ganancia_porcentaje)}
    />
  );
  const cryptoRow = (i) => (
    <PerformerRow
      key={i.id}
      id={i.id}
      name={i.symbol}
      detail={i.name || i.coingecko_id || "—"}
      value={fmt(currency === "USD" ? i.value_usd : i.value_ars)}
      pct={Number(i.pnl_pct)}
    />
  );

  return (
    <div>
      <PageHeader title="Resumen" subtitle="Patrimonio consolidado IOL + crypto" />

      <div className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="sm:col-span-2">
            <KpiCard hero label="Patrimonio total" value={fmt(total)} sub={currency} />
          </div>
          <KpiCard label="IOL" value={fmt(iolShown)} sub={share(iolShown)} />
          <KpiCard label="Crypto" value={fmt(cryptoShown)} sub={share(cryptoShown)} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-stretch">
          <div className="lg:col-span-2">
            <PortfolioLineChart
              data={snaps.data || []}
              selectedClass={selectedClass}
              period={snapPeriod}
              onPeriodChange={setSnapPeriod}
              title="Evolución IOL"
              className="h-full min-h-[22rem]"
            />
          </div>
          <AssetDonutChart
            data={kpis.data?.distribucion_por_clase || []}
            selectedClass={selectedClass}
            onSelect={setSelectedClass}
            title="Distribución IOL"
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-stretch">
          <div className="lg:col-span-2">
            <PortfolioLineChart
              data={cryptoSn.data || []}
              period={cryptoSnapPeriod}
              onPeriodChange={setCryptoSnapPeriod}
              title="Evolución crypto"
              className="h-full min-h-[22rem]"
            />
          </div>
          {cryptoDist.length > 0 ? (
            <AssetDonutChart data={cryptoDist} title="Distribución crypto" />
          ) : (
            <Card title="Distribución crypto">
              <div className="text-sm text-textMuted">Sin monedas con precio en vivo.</div>
            </Card>
          )}
        </div>

        <OperationsBarChart
          data={opsByBucket}
          title="Cobrado por símbolo"
          subtitle={`Renta + dividendos + amortizaciones · ${currency}`}
          valueLabel="Cobrado"
          period={opsPeriod}
          onPeriodChange={setOpsPeriod}
        />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card title="Mejores tenencias IOL" subtitle="Ganancia sobre costo">
            <PerformerList items={performers.top} empty="Ninguna tenencia en ganancia." render={holdingRow} />
          </Card>
          <Card title="Peores tenencias IOL" subtitle="Pérdida sobre costo">
            <PerformerList items={performers.worst} empty="Ninguna tenencia en pérdida." render={holdingRow} />
          </Card>
          <Card title="Mejores crypto" subtitle="Ganancia sobre costo">
            <PerformerList items={cryptoPerformers.top} empty="Ninguna moneda en ganancia." render={cryptoRow} />
          </Card>
          <Card title="Peores crypto" subtitle="Pérdida sobre costo">
            <PerformerList items={cryptoPerformers.worst} empty="Ninguna moneda en pérdida." render={cryptoRow} />
          </Card>
        </div>
      </div>
    </div>
  );
}
