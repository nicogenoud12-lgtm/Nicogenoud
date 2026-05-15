import { api } from "./client";

export const listCryptoHoldings = () =>
  api.get("/crypto/holdings").then((r) => r.data);

export const createCryptoHolding = (payload) =>
  api.post("/crypto/holdings", payload).then((r) => r.data);

export const updateCryptoHolding = (id, payload) =>
  api.put(`/crypto/holdings/${id}`, payload).then((r) => r.data);

export const deleteCryptoHolding = (id) =>
  api.delete(`/crypto/holdings/${id}`).then((r) => r.data);
