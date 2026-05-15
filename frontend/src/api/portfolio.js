import { api } from "./client";

export const getHoldings = (refresh = false) =>
  api.get("/portfolio/holdings", { params: { refresh } }).then((r) => r.data);

export const getKpis = () => api.get("/portfolio/kpis").then((r) => r.data);
