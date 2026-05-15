const fmtAR = new Intl.NumberFormat("es-AR", {
  style: "currency",
  currency: "ARS",
  maximumFractionDigits: 2,
});
const fmtUS = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});
const fmtNum = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 4 });
const fmtPct = new Intl.NumberFormat("es-AR", {
  style: "percent",
  maximumFractionDigits: 2,
});

export const formatARS = (n) => fmtAR.format(Number(n || 0));
export const formatUSD = (n) => fmtUS.format(Number(n || 0));
export const formatMoney = (n, currency) =>
  currency === "USD" ? formatUSD(n) : formatARS(n);
export const formatNumber = (n) => fmtNum.format(Number(n || 0));
export const formatPct = (n) => fmtPct.format(Number(n || 0) / 100);

export function formatDate(d) {
  if (!d) return "";
  const date = typeof d === "string" ? new Date(d) : d;
  return date.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function formatDateShort(d) {
  if (!d) return "";
  const date = typeof d === "string" ? new Date(d) : d;
  return date.toLocaleDateString("es-AR", { day: "2-digit", month: "short" });
}
