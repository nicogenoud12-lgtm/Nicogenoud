import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { generateInsight, getLatestInsight } from "../api/insights";
import Card from "./Card.jsx";

function SparkIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z" />
      <path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z" />
    </svg>
  );
}

function formatStamp(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return "";
  return d.toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function BulletList({ items }) {
  if (!items?.length) return <div className="text-sm text-textMuted">—</div>;
  return (
    <ul className="space-y-1.5">
      {items.map((t, i) => (
        <li key={i} className="flex gap-2 text-sm text-textSecondary">
          <span className="text-textMuted select-none">·</span>
          <span>{t}</span>
        </li>
      ))}
    </ul>
  );
}

export default function AiInsightCard() {
  const qc = useQueryClient();
  const latest = useQuery({ queryKey: ["ai-insight"], queryFn: getLatestInsight, staleTime: 300_000 });
  const gen = useMutation({
    mutationFn: generateInsight,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai-insight"] }),
  });

  if (latest.isLoading) return null;

  const enabled = latest.data?.enabled;
  const insight = latest.data?.insight;
  const c = insight?.content_json;

  const action = enabled && (
    <button onClick={() => gen.mutate()} disabled={gen.isPending} className="btn-secondary h-8 text-xs">
      <SparkIcon />
      {gen.isPending ? "Analizando…" : insight ? "Regenerar" : "Generar"}
    </button>
  );

  const subtitle = insight
    ? `Generado con IA · ${formatStamp(insight.created_at)}`
    : "Análisis de la cartera generado con IA";

  return (
    <Card title="Resumen del día" subtitle={subtitle} action={action}>
      {!enabled ? (
        <div className="notice">
          Para activarlo, agregá <code className="font-mono text-xs">ANTHROPIC_API_KEY</code> en{" "}
          <code className="font-mono text-xs">backend/.env</code> y rebuildeá el backend.
        </div>
      ) : gen.isPending ? (
        <div className="text-sm text-textMuted">Analizando la cartera. Puede tardar hasta un minuto.</div>
      ) : (
        <>
          {gen.isError && (
            <div className="notice mb-4">
              {gen.error?.response?.data?.detail || "No se pudo generar el resumen."}
            </div>
          )}
          {!c ? (
            <div className="text-sm text-textMuted">
              Todavía no hay resumen. Se genera solo de lunes a viernes después del cierre, o tocá Generar.
            </div>
          ) : (
            <div className="space-y-5">
              <div>
                <div className="text-[15px] font-medium text-text">{c.titulo}</div>
                <div className="mt-2 space-y-2 text-sm leading-relaxed text-textSecondary">
                  {String(c.resumen_dia || "")
                    .split(/\n+/)
                    .filter(Boolean)
                    .map((p, i) => (
                      <p key={i}>{p}</p>
                    ))}
                </div>
              </div>

              <div>
                <div className="label mb-2">Recomendaciones</div>
                <ul className="divide-hair -my-2">
                  {(c.recomendaciones || []).map((r, i) => (
                    <li key={i} className="flex items-start gap-3 py-2">
                      <span className="chip shrink-0 w-24 justify-center">{r.accion}</span>
                      <div className="min-w-0 text-sm">
                        <span className="font-medium text-text">{r.activo}</span>
                        <span className="text-textSecondary"> · {r.motivo}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div>
                  <div className="label mb-2">Destacados</div>
                  <BulletList items={c.destacados} />
                </div>
                <div>
                  <div className="label mb-2">Riesgos</div>
                  <BulletList items={c.riesgos} />
                </div>
              </div>

              <div className="text-xs text-textMuted">
                Generado automáticamente a partir de los datos de la cartera. No es asesoramiento financiero.
              </div>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
