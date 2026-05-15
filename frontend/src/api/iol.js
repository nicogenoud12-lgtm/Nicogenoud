import { api } from "./client";

export const iolStatus = () => api.get("/iol/status").then((r) => r.data);
export const iolConnect = (iol_username, iol_password) =>
  api.post("/iol/connect", { iol_username, iol_password }).then((r) => r.data);
export const iolDisconnect = () => api.post("/iol/disconnect").then((r) => r.data);
export const iolRefresh = () => api.post("/iol/refresh").then((r) => r.data);
