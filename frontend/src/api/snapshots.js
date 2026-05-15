import { api } from "./client";

export const listSnapshots = (days = 180) =>
  api.get("/snapshots", { params: { days } }).then((r) => r.data);
export const runSnapshotNow = () =>
  api.post("/snapshots/run-now").then((r) => r.data);
