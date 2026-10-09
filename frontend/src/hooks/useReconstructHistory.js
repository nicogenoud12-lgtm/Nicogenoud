import { reconstructSnapshots, reconstructStatus } from "../api/snapshots";
import { useBackgroundJob } from "./useBackgroundJob";

// Reconstruye la evolución diaria en el backend desde la primera operación: trae todos
// los años de operaciones, refresca tenencias y arma los snapshots con precios históricos.
export function useReconstructHistory() {
  return useBackgroundJob({
    key: "reconstruct",
    start: () => reconstructSnapshots(),
    fetchStatus: reconstructStatus,
    invalidate: [["snapshots"], ["operations"], ["opsSummary"], ["opYears"], ["holdings"], ["kpis"]],
  });
}
