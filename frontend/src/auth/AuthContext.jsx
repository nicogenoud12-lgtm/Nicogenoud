import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login as apiLogin, me as apiMe } from "../api/auth";
import { setOnUnauthorized } from "../api/client";

const AuthCtx = createContext(null);
const TOKEN_KEY = "auth_token";

export function AuthProvider({ children }) {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
    navigate("/login", { replace: true });
  }, [navigate]);

  useEffect(() => {
    setOnUnauthorized(() => logout());
  }, [logout]);

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setLoading(false);
      return;
    }
    apiMe()
      .then((u) => setUser(u))
      .catch(() => localStorage.removeItem(TOKEN_KEY))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username, password) => {
    const { access_token } = await apiLogin(username, password);
    localStorage.setItem(TOKEN_KEY, access_token);
    const u = await apiMe();
    setUser(u);
    return u;
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const u = await apiMe();
      setUser(u);
    } catch {
      /* ignore */
    }
  }, []);

  return (
    <AuthCtx.Provider value={{ user, loading, login, logout, refreshUser }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
