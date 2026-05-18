export const PERIODS = [
  { label: "1S",  days: 7,    title: "Última semana" },
  { label: "1M",  days: 30,   title: "Último mes" },
  { label: "3M",  days: 90,   title: "Últimos 3 meses" },
  { label: "6M",  days: 180,  title: "Últimos 6 meses" },
  { label: "YTD", days: null, title: "Lo que va del año" },
  { label: "12M", days: 365,  title: "Últimos 12 meses" },
  { label: "MAX", days: 3650, title: "Histórico completo" },
];

function ytdDays() {
  const now = new Date();
  const jan1 = new Date(now.getFullYear(), 0, 1);
  return Math.max(1, Math.ceil((now - jan1) / 86400000));
}

export function periodToDays(label) {
  const p = PERIODS.find((x) => x.label === label);
  if (!p) return 365;
  return p.label === "YTD" ? ytdDays() : p.days;
}

export function periodToDates(label) {
  const days = periodToDays(label);
  const to = new Date();
  const from = new Date(to);
  from.setDate(from.getDate() - days);
  const fmt = (d) => d.toISOString().slice(0, 10);
  return { fromDate: fmt(from), toDate: fmt(to), days };
}
