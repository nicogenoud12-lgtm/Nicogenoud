function cssVar(name, fallback) {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v ? `rgb(${v})` : fallback;
}

export function useChartTokens() {
  return {
    axis: cssVar("--c-text-muted", "rgb(148,163,184)"),
    grid: cssVar("--c-border", "rgb(38,50,71)"),
    accent: cssVar("--c-accent", "rgb(96,165,250)"),
    success: cssVar("--c-success", "rgb(34,197,94)"),
    danger: cssVar("--c-danger", "rgb(248,113,113)"),
    tooltipBg: cssVar("--c-surface", "rgb(17,24,39)"),
    tooltipBorder: cssVar("--c-border", "rgb(38,50,71)"),
    text: cssVar("--c-text", "rgb(229,231,235)"),
  };
}

export const palette = [
  "#60a5fa",
  "#34d399",
  "#fbbf24",
  "#f87171",
  "#a78bfa",
  "#22d3ee",
  "#fb923c",
  "#f472b6",
];
