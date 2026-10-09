import { reconstructSnapshots, reconstructStatus } from "../api/snapshots";
import { useBackgroundJob } from "./useBackgroundJob";

// Reconstruye la evolución diaria del último año en el backend: trae las operaciones
// del período, refresca tenencias y arma los snapshots con precios históricos.
export function useReconstructHistory() {
  return useBackgroundJob({
    key: "reconstruct",
    start: () => reconstructSnapshots(365),
    fetchStatus: reconstructStatus,
    invalidate: [["snapshots"], ["operations"], ["opsSummary"], ["opYears"], ["holdings"], ["kpis"]],
  });
}
