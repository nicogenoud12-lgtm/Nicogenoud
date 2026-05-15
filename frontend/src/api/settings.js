import { api } from "./client";

export const getSettings = () => api.get("/settings").then((r) => r.data);
export const updateSettings = (settings) =>
  api.put("/settings", { settings }).then((r) => r.data);
