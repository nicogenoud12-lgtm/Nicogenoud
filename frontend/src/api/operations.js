import { api } from "./client";

export const listOperations = (params = {}) =>
  api.get("/operations", { params }).then((r) => r.data);

export const syncOperations = (year = 2026) =>
  api.post("/operations/sync", null, { params: { year } }).then((r) => r.data);

export const operationsSummary = (year = 2026) =>
  api.get("/operations/summary", { params: { year } }).then((r) => r.data);
