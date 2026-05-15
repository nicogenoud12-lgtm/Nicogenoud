import { createContext, useContext, useEffect, useState } from "react";

const STORAGE_KEY = "theme";
const ThemeCtx = createContext({ theme: "dark", toggle: () => {} });

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    if (typeof window === "undefined") return "dark";
    return localStorage.getItem(STORAGE_KEY) || "dark";
  });

  useEffect(() => {
    const html = document.documentElement;
    if (theme === "dark") html.classList.add("dark");
    else html.classList.remove("dark");
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  return (
    <ThemeCtx.Provider
      value={{
        theme,
        toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")),
      }}
    >
      {children}
    </ThemeCtx.Provider>
  );
}

export const useTheme = () => useContext(ThemeCtx);
