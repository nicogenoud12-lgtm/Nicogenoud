import { useTheme } from "../../theme/ThemeProvider.jsx";

// Paleta categórica validada (CVD y contraste) — mismo orden en ambos modos,
// con pasos propios para el fondo oscuro. Nunca se cicla: más de 8 → "Otros".
const CATEGORICAL = {
  light: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
  dark: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
};

const CHROME = {
  light: {
    axis: "#787772",
    grid: "#eeede9",
    baseline: "#d9d8d2",
    text: "#111110",
    textSecondary: "#52514e",
    surface: "#ffffff",
    border: "#e5e4df",
    accent: "#2a78d6",
    success: "#007a33",
    danger: "#c42b2b",
  },
  dark: {
    axis: "#898781",
    grid: "#232322",
    baseline: "#383835",
    text: "#f3f3f0",
    textSecondary: "#c3c2b7",
    surface: "#161615",
    border: "#282826",
    accent: "#3987e5",
    success: "#34c76e",
    danger: "#ec6767",
  },
};

// El color sigue a la entidad, no a su ranking: cada clase tiene su slot fijo.
const CLASS_SLOT = {
  CEDEAR: 0,
  "Acción": 1,
  Bono: 2,
  ON: 3,
  FCI: 4,
  Letra: 5,
  Otro: 6,
  Caucion: 7,
};

export function useChartTokens() {
  const { theme } = useTheme();
  const mode = theme === "dark" ? "dark" : "light";
  const c = CHROME[mode];
  return {
    ...c,
    mode,
    categorical: CATEGORICAL[mode],
    tooltipBg: c.surface,
    tooltipBorder: c.border,
  };
}

/** Color estable para una entidad: slot fijo si es una clase conocida, si no por orden alfabético. */
export function colorFor(name, allNames, categorical) {
  if (name in CLASS_SLOT) return categorical[CLASS_SLOT[name]];
  const sorted = [...allNames].filter((n) => !(n in CLASS_SLOT)).sort();
  const idx = sorted.indexOf(name);
  return idx >= 0 && idx < categorical.length ? categorical[idx] : null;
}

export const tooltipStyle = (t) => ({
  background: t.surface,
  border: `1px solid ${t.border}`,
  borderRadius: 8,
  color: t.text,
  fontSize: 12,
  padding: "8px 10px",
  boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
});

// Ticks compactos con la precisión justa para que dos ticks no repitan etiqueta (2.0M / 2.0M)
export const compactNumber = (v) => {
  const sign = v < 0 ? "-" : "";
  const abs = Math.abs(v);
  const trim = (n, d) => String(Number(n.toFixed(d)));
  if (abs >= 1_000_000) return `${sign}${trim(abs / 1_000_000, abs >= 10_000_000 ? 1 : 2)}M`;
  if (abs >= 1_000) return `${sign}${trim(abs / 1_000, abs >= 100_000 ? 0 : 1)}k`;
  return `${sign}${Math.round(abs)}`;
};
