import { api } from "./client";

export const getDolarCurrent = (source) =>
  api.get("/dolar/current", { params: source ? { source } : {} }).then((r) => r.data);
export const getDolarHistory = (source, days = 90) =>
  api.get("/dolar/history", { params: { source, days } }).then((r) => r.data);
