import { api } from "./client";

export const listOperations = (params = {}) =>
  api.get("/operations", { params }).then((r) => r.data);

export const syncOperations = (year = 2026) =>
  api.post("/operations/sync", null, { params: { year } }).then((r) => r.data);

export const operationsSummary = ({ fromDate, toDate } = {}) =>
  api.get("/operations/summary", { params: { from_date: fromDate, to_date: toDate } }).then((r) => r.data);
