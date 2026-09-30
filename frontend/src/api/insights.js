import { api } from "./client";

export const getLatestInsight = () => api.get("/insights/latest").then((r) => r.data);

export const generateInsight = () =>
  api.post("/insights/generate", null, { timeout: 240_000 }).then((r) => r.data);
