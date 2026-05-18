import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import LoginScreen from "./auth/LoginScreen.jsx";
import ProtectedRoute from "./auth/ProtectedRoute.jsx";
import ResumenScreen from "./screens/ResumenScreen.jsx";
import TenenciasScreen from "./screens/TenenciasScreen.jsx";
import OperacionesScreen from "./screens/OperacionesScreen.jsx";
import AnalisisScreen from "./screens/AnalisisScreen.jsx";
import CryptoScreen from "./screens/CryptoScreen.jsx";
import AjustesScreen from "./screens/AjustesScreen.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginScreen />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<AnalisisScreen />} />
        <Route path="inversiones" element={<ResumenScreen />} />
        <Route path="tenencias" element={<TenenciasScreen />} />
        <Route path="operaciones" element={<OperacionesScreen />} />
        <Route path="analisis" element={<Navigate to="/" replace />} />
        <Route path="crypto" element={<CryptoScreen />} />
        <Route path="ajustes" element={<AjustesScreen />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
