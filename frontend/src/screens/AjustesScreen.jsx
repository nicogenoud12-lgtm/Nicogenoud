import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { iolConnect, iolDisconnect, iolRefresh, iolStatus } from "../api/iol";
import { getSettings, updateSettings } from "../api/settings";
import { runSnapshotNow } from "../api/snapshots";
import { reconstructErrorText, useReconstructHistory } from "../hooks/useReconstructHistory";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import PageHeader from "../components/PageHeader.jsx";
import { formatDate } from "../utils/format";

const DOLAR_SOURCES = ["MEP", "CCL", "Blue", "Oficial"];

// Sección de configuración: descripción a la izquierda, controles a la derecha.
function SettingsSection({ title, description, children }) {
  return (
    <section className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-8 py-8 first:pt-0">
      <div>
        <h2 className="section-title">{title}</h2>
        {description && <p className="text-[13px] text-textMuted mt-1 leading-relaxed">{description}</p>}
      </div>
      <div className="md:col-span-2 card card-pad space-y-4">{children}</div>
    </section>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      <div className="mt-1.5">{children}</div>
    </label>
  );
}

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
  const handleDisconnect = () => {
    if (window.confirm("Esto borra las credenciales IOL guardadas y cierra la sesión. ¿Seguro?")) {
      disconnect.mutate();
    }
  };
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

  const rebuild = useReconstructHistory();

  if (status.isLoading || settings.isLoading) return <LoadingSpinner />;

  const st = status.data || {};
  return (
    <div className="max-w-4xl">
      <PageHeader title="Ajustes" subtitle="Conexión con IOL, cotización y tareas programadas" />

      {feedback && (
        <div className="notice mb-6" role="status">
          <span className={`font-medium ${feedback.type === "ok" ? "text-success" : "text-danger"}`}>
            {feedback.type === "ok" ? "Listo" : "Error"}
          </span>
          <span>{feedback.text}</span>
        </div>
      )}

      <div className="divide-hair">
        <SettingsSection
          title="Conexión IOL"
          description="Las credenciales se guardan encriptadas en la base. La sesión se renueva sola cada 12 horas."
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm">
              <span className={`h-2 w-2 rounded-full ${st.connected ? "bg-success" : "bg-danger"}`} />
              <span className="font-medium text-text">{st.connected ? "Conectado" : "Desconectado"}</span>
            </div>
            {st.connected && <span className="text-sm text-textMuted">{st.iol_username}</span>}
          </div>

          {st.connected ? (
            <>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-[13px]">
                <div>
                  <dt className="text-textMuted">Conectado</dt>
                  <dd className="text-text mt-0.5">{formatDate(st.connected_at)}</dd>
                </div>
                <div>
                  <dt className="text-textMuted">Access token vence</dt>
                  <dd className="text-text mt-0.5">{formatDate(st.access_expires_at)}</dd>
                </div>
                {st.refresh_expires_at && (
                  <div>
                    <dt className="text-textMuted">Refresh token vence</dt>
                    <dd className="text-text mt-0.5">{formatDate(st.refresh_expires_at)}</dd>
                  </div>
                )}
                {st.last_keepalive_at && (
                  <div>
                    <dt className="text-textMuted">Último keep-alive</dt>
                    <dd className="text-text mt-0.5">{formatDate(st.last_keepalive_at)}</dd>
                  </div>
                )}
              </dl>
              {st.last_error && <div className="text-danger text-xs">Último error: {st.last_error}</div>}
              <div className="flex gap-2 pt-1">
                <button className="btn-secondary" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
                  Renovar token
                </button>
                <button className="btn-danger" onClick={handleDisconnect} disabled={disconnect.isPending}>
                  Desconectar
                </button>
              </div>
            </>
          ) : (
            <form
              className="space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                connect.mutate();
              }}
            >
              <Field label="Usuario IOL">
                <input
                  className="input"
                  value={iolUsername}
                  onChange={(e) => setIolUsername(e.target.value)}
                  required
                  autoComplete="off"
                />
              </Field>
              <Field label="Contraseña IOL">
                <input
                  className="input"
                  type="password"
                  value={iolPassword}
                  onChange={(e) => setIolPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                />
              </Field>
              <button className="btn-primary" type="submit" disabled={connect.isPending}>
                {connect.isPending ? "Conectando…" : "Conectar"}
              </button>
            </form>
          )}
        </SettingsSection>

        <SettingsSection
          title="Cotización del dólar"
          description="Se usa para convertir ARS a USD en las KPIs y en los snapshots diarios. Fuente: dolarapi.com."
        >
          <div className="segmented" role="radiogroup" aria-label="Fuente de dólar">
            {DOLAR_SOURCES.map((s) => (
              <button
                key={s}
                type="button"
                role="radio"
                aria-checked={dolarSource === s}
                onClick={() => setDolarSource(s)}
                className={`segmented-item ${dolarSource === s ? "segmented-item-active" : ""}`}
              >
                {s}
              </button>
            ))}
          </div>
          <div className="text-xs text-textMuted">Se aplica al guardar.</div>
        </SettingsSection>

        <SettingsSection
          title="Tareas programadas"
          description="Snapshot diario de la cartera y sincronización de operaciones con IOL."
        >
          <label className="flex items-center gap-2.5 text-sm text-text">
            <input
              type="checkbox"
              className="h-4 w-4 accent-current"
              checked={schedulerEnabled}
              onChange={(e) => setSchedulerEnabled(e.target.checked)}
            />
            Habilitadas
          </label>
          <Field label="Horario del snapshot (formato cron)">
            <input
              className="input max-w-xs num"
              value={snapshotCron}
              onChange={(e) => setSnapshotCron(e.target.value)}
              placeholder="55 23 * * *"
            />
          </Field>
          <div className="flex flex-wrap gap-2 pt-1">
            <button className="btn-primary" onClick={() => saveSettings.mutate()} disabled={saveSettings.isPending}>
              Guardar cambios
            </button>
            <button className="btn-secondary" onClick={() => runSnap.mutate()} disabled={runSnap.isPending}>
              {runSnap.isPending ? "Generando…" : "Generar snapshot ahora"}
            </button>
          </div>
        </SettingsSection>

        <SettingsSection
          title="Evolución histórica"
          description="Arma la evolución diaria del último año a partir de las tenencias actuales, las operaciones y los precios históricos de IOL. No pisa los snapshots reales; se puede volver a correr. Los FCI se valúan a la cuotaparte actual."
        >
          <div className="flex flex-wrap items-center gap-3">
            <button className="btn-secondary" onClick={() => rebuild.mutate()} disabled={rebuild.isPending}>
              {rebuild.isPending ? rebuild.step : "Reconstruir el último año"}
            </button>
            {rebuild.isSuccess && (
              <span className="text-sm text-textMuted">
                {rebuild.data.creados + rebuild.data.actualizados} días armados desde el{" "}
                {rebuild.data.desde.split("-").reverse().join("/")}
              </span>
            )}
            {rebuild.isError && <span className="text-sm text-danger">{reconstructErrorText(rebuild.error)}</span>}
          </div>
        </SettingsSection>
      </div>
    </div>
  );
}
