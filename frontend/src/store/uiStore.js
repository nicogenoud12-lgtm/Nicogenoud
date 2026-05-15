import { create } from "zustand";

const KEY = "ui:currency";

export const useUiStore = create((set) => ({
  currency: (typeof window !== "undefined" && localStorage.getItem(KEY)) || "ARS",
  sidebarOpen: false,
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
