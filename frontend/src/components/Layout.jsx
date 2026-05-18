import { NavLink, Outlet } from "react-router-dom";
import { useUiStore } from "../store/uiStore";
import { useTheme } from "../theme/ThemeProvider.jsx";
import { useAuth } from "../auth/AuthContext.jsx";
import CurrencyToggle from "./CurrencyToggle.jsx";

const NAV = [
  { to: "/", label: "Resumen", end: true },
  { to: "/tenencias", label: "Tenencias" },
  { to: "/operaciones", label: "Operaciones 2026" },
  { to: "/analisis", label: "Análisis" },
  { to: "/crypto", label: "Crypto" },
  { to: "/ajustes", label: "Ajustes" },
];

export default function Layout() {
  const { sidebarOpen, toggleSidebar, closeSidebar } = useUiStore();
  const { theme, toggle } = useTheme();
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen flex">
      {/* Mobile drawer overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
          onClick={closeSidebar}
        />
      )}

      <aside
        className={`fixed md:static z-40 w-64 h-screen bg-surface border-r border-border flex flex-col transition-transform ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <div className="px-5 py-5 border-b border-border">
          <div className="text-lg font-semibold tracking-tight">Investments</div>
          <div className="text-xs text-textMuted mt-0.5">{user?.username}</div>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              onClick={closeSidebar}
              className={({ isActive }) =>
                `block rounded-lg px-3 py-2 text-sm transition ${
                  isActive
                    ? "bg-accentSoft text-text font-medium"
                    : "text-textMuted hover:bg-surfaceAlt hover:text-text"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-border space-y-2">
          <button onClick={toggle} className="btn-secondary w-full">
            {theme === "dark" ? "🌞 Modo claro" : "🌙 Modo oscuro"}
          </button>
          <button onClick={logout} className="btn-secondary w-full">
            Cerrar sesión
          </button>
        </div>
      </aside>

      <div className="flex-1 md:ml-0 min-w-0 flex flex-col">
        <header className="md:hidden flex items-center justify-between px-4 py-3 border-b border-border bg-surface">
          <button
            onClick={toggleSidebar}
            className="btn-secondary p-2"
            aria-label="Abrir menú"
          >
            ☰
          </button>
          <CurrencyToggle />
        </header>
        <header className="hidden md:flex items-center justify-end px-6 py-3 border-b border-border">
          <CurrencyToggle />
        </header>
        <main className="flex-1 p-4 md:p-6 max-w-screen-2xl w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
