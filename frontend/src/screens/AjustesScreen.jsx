import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { iolConnect, iolDisconnect, iolRefresh, iolStatus } from "../api/iol";
import { getSettings, updateSettings } from "../api/settings";
import { runSnapshotNow } from "../api/snapshots";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import { formatDate } from "../utils/format";

const DOLAR_SOURCES = ["MEP", "CCL", "Blue", "Oficial"];

export default function AjustesScreen() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["iol-status"], queryFn: iolStatus });
  const settings = useQuery({ queryKey: ["settings"], queryFn: getSettings });

  const [iolUsername, setIolUsername] = useState("");
  const [iolPassword, setIolPassword] = useState("");
  const [feedback, setFeedback] = useState(null);

  const [dolarSource, setDolarSource] = useState("MEP");
  const [snapshotCron, setSnapshotCron] = useState("");
  const [schedulerEnabled, setSchedulerEnabled] = useState(true);

  useEffect(() => {
    if (settings.data?.settings) {
      const s = settings.data.settings;
      setDolarSource(s.dolar_source || "MEP");
      setSnapshotCron(s.snapshot_cron || "55 23 * * *");
      setSchedulerEnabled((s.scheduler_enabled || "true").toLowerCase() === "true");
    }
  }, [settings.data]);

  const connect = useMutation({
    mutationFn: () => iolConnect(iolUsername, iolPassword),
    onSuccess: () => {
      setFeedback({ type: "ok", text: "Conectado a IOL" });
      setIolPassword("");
      qc.invalidateQueries({ queryKey: ["iol-status"] });
    },
    onError: (e) =>
      setFeedback({
        type: "err",
        text: e?.response?.data?.detail || "Falló la conexión a IOL",
      }),
  });
  const disconnect = useMutation({
    mutationFn: iolDisconnect,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["iol-status"] }),
  });
  const refresh = useMutation({
    mutationFn: iolRefresh,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["iol-status"] }),
  });
  const saveSettings = useMutation({
    mutationFn: () =>
      updateSettings({
        dolar_source: dolarSource,
        snapshot_cron: snapshotCron,
        scheduler_enabled: schedulerEnabled ? "true" : "false",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      setFeedback({ type: "ok", text: "Configuración guardada" });
    },
  });
  const runSnap = useMutation({
    mutationFn: runSnapshotNow,
    onSuccess: (snap) => {
      qc.invalidateQueries({ queryKey: ["snapshots", 90] });
      qc.invalidateQueries({ queryKey: ["snapshots", 3650] });
      setFeedback({
        type: "ok",
        text: `Snapshot creado para ${snap?.date || "hoy"}`,
      });
    },
    onError: (e) =>
      setFeedback({
        type: "err",
        text: e?.response?.data?.detail || "No se pudo generar snapshot",
      }),
  });

  if (status.isLoading || settings.isLoading) return <LoadingSpinner />;

  const st = status.data || {};
  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-xl font-semibold">Ajustes</h1>

      {feedback && (
        <div
          className={`text-sm rounded-lg px-3 py-2 border ${
            feedback.type === "ok"
              ? "bg-success/10 border-success/30 text-success"
              : "bg-danger/10 border-danger/30 text-danger"
          }`}
        >
          {feedback.text}
        </div>
      )}

      <section className="card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-base font-medium">Conexión IOL</div>
            <div className="text-xs text-textMuted">
              Tus credenciales se guardan encriptadas (Fernet) en la DB.
            </div>
          </div>
          <span
            className={`chip ${
              st.connected
                ? "bg-success/10 text-success border-success/30"
                : "bg-danger/10 text-danger border-danger/30"
            }`}
          >
            {st.connected ? "Conectado" : "Desconectado"}
          </span>
        </div>

        {st.connected ? (
          <div className="space-y-2 text-sm">
            <div>
              <span className="text-textMuted">Usuario IOL:</span>{" "}
              <span className="font-medium">{st.iol_username}</span>
            </div>
            <div className="text-textMuted">
              Conectado el {formatDate(st.connected_at)} · Token expira{" "}
              {formatDate(st.access_expires_at)}
            </div>
            {st.last_error && (
              <div className="text-danger text-xs">Último error: {st.last_error}</div>
            )}
            <div className="flex gap-2 pt-2">
              <button
                className="btn-secondary"
                onClick={() => refresh.mutate()}
                disabled={refresh.isPending}
              >
                ↻ Refresh token
              </button>
              <button
                className="btn-danger"
                onClick={() => disconnect.mutate()}
                disabled={disconnect.isPending}
              >
                Desconectar
              </button>
            </div>
          </div>
        ) : (
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              connect.mutate();
            }}
          >
            <div>
              <label className="label">Usuario IOL</label>
              <input
                className="input mt-1"
                value={iolUsername}
                onChange={(e) => setIolUsername(e.target.value)}
                required
                autoComplete="off"
              />
            </div>
            <div>
              <label className="label">Contraseña IOL</label>
              <input
                className="input mt-1"
                type="password"
                value={iolPassword}
                onChange={(e) => setIolPassword(e.target.value)}
                required
                autoComplete="new-password"
              />
            </div>
            <button className="btn-primary" type="submit" disabled={connect.isPending}>
              {connect.isPending ? "Conectando…" : "Conectar"}
            </button>
          </form>
        )}
      </section>

      <section className="card p-5 space-y-4">
        <div className="text-base font-medium">Fuente de dólar</div>
        <div className="flex flex-wrap gap-2">
          {DOLAR_SOURCES.map((s) => (
            <label
              key={s}
              className={`chip cursor-pointer ${
                dolarSource === s ? "bg-accent text-white border-accent" : ""
              }`}
            >
              <input
                type="radio"
                className="hidden"
                checked={dolarSource === s}
                onChange={() => setDolarSource(s)}
              />
              {s}
            </label>
          ))}
        </div>
        <p className="text-xs text-textMuted">
          Se usa para convertir ARS→USD en KPIs y en los snapshots diarios. Fuente:
          dolarapi.com.
        </p>
      </section>

      <section className="card p-5 space-y-4">
        <div className="text-base font-medium">Scheduler</div>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={schedulerEnabled}
            onChange={(e) => setSchedulerEnabled(e.target.checked)}
          />
          <span className="text-sm">Habilitado (snapshot + sync operaciones diario)</span>
        </label>
        <div>
          <label className="label">Cron snapshot (formato cron)</label>
          <input
            className="input mt-1 max-w-xs"
            value={snapshotCron}
            onChange={(e) => setSnapshotCron(e.target.value)}
            placeholder="55 23 * * *"
          />
        </div>
        <div className="flex gap-2">
          <button
            className="btn-primary"
            onClick={() => saveSettings.mutate()}
            disabled={saveSettings.isPending}
          >
            Guardar
          </button>
          <button
            className="btn-secondary"
            onClick={() => runSnap.mutate()}
            disabled={runSnap.isPending}
          >
            {runSnap.isPending ? "Generando…" : "Ejecutar snapshot ahora"}
          </button>
        </div>
      </section>
    </div>
  );
}
