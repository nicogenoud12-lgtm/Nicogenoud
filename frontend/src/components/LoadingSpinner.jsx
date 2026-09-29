export default function LoadingSpinner({ label = "Cargando" }) {
  return (
    <div className="flex items-center gap-2.5 text-textMuted text-sm py-10" role="status">
      <span className="h-3.5 w-3.5 rounded-full border-2 border-border border-t-textMuted animate-spin" />
      {label}
    </div>
  );
}
