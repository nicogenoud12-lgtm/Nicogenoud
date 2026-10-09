import { api } from "./client";

export const listOperations = (params = {}) =>
  api.get("/operations", { params }).then((r) => r.data);

export const syncOperations = (year) =>
  api.post("/operations/sync", null, { params: { year } }).then((r) => r.data);

export const operationYears = () => api.get("/operations/years").then((r) => r.data);

export const operationsSummary = ({ fromDate, toDate } = {}) =>
  api.get("/operations/summary", { params: { from_date: fromDate, to_date: toDate } }).then((r) => r.data);

export const syncHistory = () => api.post("/operations/sync-history").then((r) => r.data);
export const syncHistoryStatus = () => api.get("/operations/sync-history").then((r) => r.data);
