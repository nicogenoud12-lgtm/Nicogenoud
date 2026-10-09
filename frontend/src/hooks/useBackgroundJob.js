import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

// Tarea larga que corre en el backend (Cloudflare corta los requests de más de ~100 s):
// `start` la lanza y devuelve su estado; `fetchStatus` se consulta cada 2 s mientras corre.
// Al entrar a la pantalla se retoma una tarea que ya estaba corriendo.
export function useBackgroundJob({ key, start, fetchStatus, invalidate = [] }) {
  const qc = useQueryClient();
  const queryKey = ["job", key];
  const [startedHere, setStartedHere] = useState(false);

  const status = useQuery({
    queryKey,
    queryFn: fetchStatus,
    refetchInterval: (q) => (q.state.data?.estado === "corriendo" ? 2000 : false),
  });
  const launch = useMutation({
    mutationFn: start,
    onSuccess: (job) => qc.setQueryData(queryKey, job),
  });

  const job = status.data;
  const estado = job?.estado;
  const prev = useRef(estado);
  useEffect(() => {
    if (prev.current === "corriendo" && estado && estado !== "corriendo") {
      invalidate.forEach((k) => qc.invalidateQueries({ queryKey: k }));
    }
    prev.current = estado;
  }, [estado]); // eslint-disable-line react-hooks/exhaustive-deps

  const running = launch.isPending || estado === "corriendo";
  const launchError = launch.error?.response?.data?.detail || (launch.isError ? "No se pudo iniciar" : null);
  return {
    run: () => {
      setStartedHere(true);
      launch.mutate();
    },
    running,
    step: job?.paso,
    // Resultado o error sólo de la tarea lanzada en esta visita, no de una vieja
    result: startedHere && estado === "ok" ? job.resultado : null,
    error: launchError || (startedHere && estado === "error" ? job.error : null),
  };
}
