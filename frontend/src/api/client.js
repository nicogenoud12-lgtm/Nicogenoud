import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export const api = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("auth_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let onUnauthorized = null;
export function setOnUnauthorized(cb) {
  onUnauthorized = cb;
}

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 && onUnauthorized) onUnauthorized();
    return Promise.reject(err);
  },
);
