import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useUiStore } from "../store/uiStore";
import { useTheme } from "../theme/ThemeProvider.jsx";
import { useAuth } from "../auth/AuthContext.jsx";
import CurrencyToggle from "./CurrencyToggle.jsx";

const NAV = [
  { to: "/", label: "Resumen", end: true },
  { to: "/inversiones", label: "Inversiones" },
  { to: "/tenencias", label: "Tenencias" },
  { to: "/operaciones", label: "Operaciones" },
  { to: "/crypto", label: "Crypto" },
];

const iconProps = {
  width: 16,
  height: 16,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
};

const SunIcon = () => (
  <svg {...iconProps}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </svg>
);
const MoonIcon = () => (
  <svg {...iconProps}>
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
  </svg>
);
const MenuIcon = () => (
  <svg {...iconProps}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </svg>
);

function NavItem({ to, label, end, onClick }) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      className={({ isActive }) =>
        `flex items-center h-8 rounded-md px-2.5 text-sm transition-colors ${
          isActive ? "bg-surfaceAlt text-text font-medium" : "text-textMuted hover:text-text"
        }`
      }
    >
      {label}
    </NavLink>
  );
}

export default function Layout() {
  const { sidebarOpen, toggleSidebar, closeSidebar } = useUiStore();
  const { theme, toggle } = useTheme();
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const current = [...NAV, { to: "/ajustes", label: "Ajustes" }].find((n) =>
    n.end ? pathname === n.to : pathname.startsWith(n.to)
  );

  return (
    <div className="min-h-screen flex">
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/40 z-30 md:hidden" onClick={closeSidebar} />
      )}

      <aside
        className={`fixed md:sticky md:top-0 z-40 w-56 h-screen shrink-0 bg-bg border-r border-border flex flex-col transition-transform ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <div className="px-5 h-14 flex items-center gap-2.5">
          <span className="h-5 w-5 rounded-md bg-text grid place-items-center" aria-hidden>
            <span className="h-2 w-2 rounded-sm bg-bg" />
          </span>
          <span className="text-sm font-semibold tracking-tight">Cartera</span>
        </div>

        <nav className="flex-1 px-3 pt-2 space-y-0.5" aria-label="Principal">
          {NAV.map((n) => (
            <NavItem key={n.to} {...n} onClick={closeSidebar} />
          ))}
        </nav>

        <div className="px-3 pb-4 space-y-0.5">
          <NavItem to="/ajustes" label="Ajustes" onClick={closeSidebar} />
          <div className="flex items-center justify-between gap-2 pt-3 mt-3 border-t border-border px-2.5">
            <div className="min-w-0">
              <div className="text-sm text-text truncate">{user?.username}</div>
              <button onClick={logout} className="text-xs text-textMuted hover:text-text">
                Cerrar sesión
              </button>
            </div>
            <button
              onClick={toggle}
              className="btn-ghost h-8 w-8 px-0"
              aria-label={theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
              title={theme === "dark" ? "Modo claro" : "Modo oscuro"}
            >
              {theme === "dark" ? <SunIcon /> : <MoonIcon />}
            </button>
          </div>
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="sticky top-0 z-20 h-14 flex items-center justify-between gap-3 px-4 md:px-8 border-b border-border bg-bg/85 backdrop-blur">
          <div className="flex items-center gap-2 min-w-0">
            <button onClick={toggleSidebar} className="btn-ghost h-8 w-8 px-0 md:hidden" aria-label="Abrir menú">
              <MenuIcon />
            </button>
            <span className="text-sm text-textMuted truncate">{current?.label}</span>
          </div>
          <CurrencyToggle />
        </header>
        <main className="flex-1 px-4 md:px-8 py-6 md:py-8 max-w-[1400px] w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
