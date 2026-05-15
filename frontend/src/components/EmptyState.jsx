export default function EmptyState({ title, description, action }) {
  return (
    <div className="card p-8 text-center">
      <div className="text-base font-medium">{title}</div>
      {description && (
        <div className="text-sm text-textMuted mt-1">{description}</div>
      )}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}
