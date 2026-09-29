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

// "YYYY-MM-DD" sin hora: new Date() lo lee como medianoche UTC, que en
// Argentina (UTC-3) cae el día anterior. Lo armamos en hora local.
function parseDate(d) {
  if (typeof d !== "string") return d;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d);
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : new Date(d);
}

export function formatDate(d) {
  if (!d) return "";
  const date = parseDate(d);
  return date.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function formatDateShort(d) {
  if (!d) return "";
  const date = parseDate(d);
  return date.toLocaleDateString("es-AR", { day: "2-digit", month: "short" });
}
