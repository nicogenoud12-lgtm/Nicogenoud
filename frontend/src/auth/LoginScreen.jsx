import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext.jsx";

export default function LoginScreen() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const loc = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(username, password);
      const dest = loc.state?.from?.pathname || "/";
      navigate(dest, { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo iniciar sesión");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-bg">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2.5 mb-8">
          <span className="h-6 w-6 rounded-md bg-text grid place-items-center" aria-hidden>
            <span className="h-2.5 w-2.5 rounded-sm bg-bg" />
          </span>
          <span className="text-base font-semibold tracking-tight">Cartera</span>
        </div>
        <h1 className="text-xl font-semibold tracking-tight">Iniciar sesión</h1>
        <p className="text-sm text-textMuted mt-1 mb-6">Ingresá con tu usuario del dashboard.</p>
        <form onSubmit={submit} className="space-y-4">
          <label className="block">
            <span className="label">Usuario</span>
            <input
              className="input mt-1.5"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              autoComplete="username"
              required
            />
          </label>
          <label className="block">
            <span className="label">Contraseña</span>
            <input
              className="input mt-1.5"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          {error && (
            <div className="text-sm text-danger" role="alert">
              {error}
            </div>
          )}
          <button type="submit" className="btn-primary w-full" disabled={busy}>
            {busy ? "Ingresando…" : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
