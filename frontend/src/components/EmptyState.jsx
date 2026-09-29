export default function EmptyState({ title, description, action }) {
  return (
    <div className="card px-6 py-12 text-center">
      <div className="text-sm font-medium text-text">{title}</div>
      {description && <div className="text-sm text-textMuted mt-1 max-w-md mx-auto">{description}</div>}
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}
