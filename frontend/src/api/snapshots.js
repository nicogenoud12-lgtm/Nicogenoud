import { api } from "./client";

export const listSnapshots = (days = 180) =>
  api.get("/snapshots", { params: { days } }).then((r) => r.data);
export const runSnapshotNow = () =>
  api.post("/snapshots/run-now").then((r) => r.data);
// Sin `dias`: toda la historia, desde la primera operación
export const reconstructSnapshots = (dias) =>
  api.post("/snapshots/reconstruct", null, { params: dias ? { dias } : {} }).then((r) => r.data);
export const reconstructStatus = () => api.get("/snapshots/reconstruct").then((r) => r.data);
