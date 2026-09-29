// Contenedor estándar de sección: título, acción opcional a la derecha y contenido.
export default function Card({ title, subtitle, action, children, className = "", bodyClassName = "" }) {
  return (
    <section className={`card card-pad min-w-0 ${className}`}>
      {(title || action) && (
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="min-w-0">
            {title && <h2 className="section-title">{title}</h2>}
            {subtitle && <div className="text-xs text-textMuted mt-0.5">{subtitle}</div>}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}
