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
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="card p-8 w-full max-w-md">
        <h1 className="text-2xl font-semibold mb-1">Investment Dashboard</h1>
        <p className="text-textMuted text-sm mb-6">Iniciar sesión</p>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">Usuario</label>
            <input
              className="input mt-1"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              autoComplete="username"
              required
            />
          </div>
          <div>
            <label className="label">Contraseña</label>
            <input
              className="input mt-1"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          {error && (
            <div className="text-sm text-danger bg-danger/10 border border-danger/30 rounded-lg px-3 py-2">
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
