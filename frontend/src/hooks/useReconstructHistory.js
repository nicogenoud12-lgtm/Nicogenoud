import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { syncOperations } from "../api/operations";
import { reconstructSnapshots } from "../api/snapshots";

const DIAS = 365;

// Reconstruye la evolución diaria del último año: primero trae de IOL las operaciones
// del período (para saber qué se compró y vendió cada día) y después arma los snapshots
// con los precios históricos. Cada paso es un request aparte para no chocar con timeouts.
export function useReconstructHistory() {
  const qc = useQueryClient();
  const [step, setStep] = useState(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const now = new Date();
      const firstYear = new Date(now.getTime() - DIAS * 86400000).getFullYear();
      for (let y = firstYear; y <= now.getFullYear(); y++) {
        setStep(`Trayendo operaciones ${y}…`);
        await syncOperations(y);
      }
      setStep("Armando la evolución con precios históricos…");
      return reconstructSnapshots(DIAS);
    },
    onSettled: () => {
      setStep(null);
      qc.invalidateQueries({ queryKey: ["snapshots"] });
      qc.invalidateQueries({ queryKey: ["operations"] });
      qc.invalidateQueries({ queryKey: ["opsSummary"] });
      qc.invalidateQueries({ queryKey: ["opYears"] });
    },
  });

  return { ...mutation, step };
}

export function reconstructErrorText(e) {
  return e?.response?.data?.detail || "No se pudo reconstruir la evolución";
}
