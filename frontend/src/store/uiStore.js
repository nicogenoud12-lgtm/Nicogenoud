import { create } from "zustand";

const KEY = "ui:currency";
const EVO_KEY = "ui:evoMode";

function readStorage(key, fallback) {
  try {
    return (typeof window !== "undefined" && localStorage.getItem(key)) || fallback;
  } catch {
    return fallback;
  }
}

export const useUiStore = create((set) => ({
  currency: (typeof window !== "undefined" && localStorage.getItem(KEY)) || "ARS",
  sidebarOpen: false,
  // Vista del gráfico de evolución: "valor" (monto) o "rendimiento" (% sin aportes/retiros)
  evoMode: readStorage(EVO_KEY, "valor"),
  setEvoMode: (m) => {
    try {
      localStorage.setItem(EVO_KEY, m);
    } catch {
      /* sin storage: queda sólo en memoria */
    }
    set({ evoMode: m });
  },
  setCurrency: (c) => {
    if (typeof window !== "undefined") localStorage.setItem(KEY, c);
    set({ currency: c });
  },
  toggleCurrency: () =>
    set((s) => {
      const next = s.currency === "ARS" ? "USD" : "ARS";
      if (typeof window !== "undefined") localStorage.setItem(KEY, next);
      return { currency: next };
    }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  closeSidebar: () => set({ sidebarOpen: false }),
}));
