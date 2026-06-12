export default function LoadingSpinner({ className = '' }) {
  return (
    <div className={`flex items-center justify-center py-10 ${className}`}>
      <div className="spinner-ring" />
    </div>
  );
}

export function SkeletonList({ count = 3 }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }, (_, i) => (
        <div
          key={i}
          className="skeleton-card stagger-item"
          style={{ animationDelay: `${i * 50}ms` }}
        />
      ))}
    </div>
  );
}
