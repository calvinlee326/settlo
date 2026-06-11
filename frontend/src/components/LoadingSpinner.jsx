export default function LoadingSpinner({ className = '' }) {
  return (
    <div className={`flex items-center justify-center py-10 ${className}`}>
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-100 border-t-primary-600" />
    </div>
  );
}
