export default function LoadingSpinner({ label = "Cargando…" }) {
  return (
    <div className="flex items-center gap-3 text-textMuted text-sm py-6">
      <span className="inline-block h-3 w-3 rounded-full bg-accent animate-pulse" />
      {label}
    </div>
  );
}
