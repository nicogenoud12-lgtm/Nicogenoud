import { api } from "./client";

export const listCryptoHoldings = () =>
  api.get("/crypto/holdings").then((r) => r.data);

export const createCryptoHolding = (payload) =>
  api.post("/crypto/holdings", payload).then((r) => r.data);

export const updateCryptoHolding = (id, payload) =>
  api.put(`/crypto/holdings/${id}`, payload).then((r) => r.data);

export const deleteCryptoHolding = (id) =>
  api.delete(`/crypto/holdings/${id}`).then((r) => r.data);

export const sellCryptoHolding = (id, payload) =>
  api.post(`/crypto/holdings/${id}/sell`, payload).then((r) => r.data);

export const listCryptoSales = () =>
  api.get("/crypto/sales").then((r) => r.data);

export const deleteCryptoSale = (id) =>
  api.delete(`/crypto/sales/${id}`).then((r) => r.data);

export const searchCoins = (q) =>
  api.get("/crypto/search", { params: { q } }).then((r) => r.data);

export const getCryptoReport = () =>
  api.get("/crypto/report").then((r) => r.data);

export const listCryptoSnapshots = (days = 180) =>
  api.get("/crypto/snapshots", { params: { days } }).then((r) => r.data);

export const backfillCryptoSnapshots = (since) =>
  api
    .post("/crypto/backfill", null, { params: since ? { since } : {} })
    .then((r) => r.data);
