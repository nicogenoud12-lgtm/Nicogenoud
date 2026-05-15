import { api } from "./client";

export const login = (username, password) =>
  api.post("/auth/login", { username, password }).then((r) => r.data);

export const me = () => api.get("/auth/me").then((r) => r.data);
