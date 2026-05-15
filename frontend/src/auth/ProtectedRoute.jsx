import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext.jsx";

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center">
        <div className="text-textMuted">Cargando…</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" state={{ from: loc }} replace />;
  return children;
}
