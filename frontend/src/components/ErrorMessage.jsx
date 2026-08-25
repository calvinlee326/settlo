export default function ErrorMessage({ message }) {
  if (!message) return null;
  return (
    <div className="rounded-card border border-ink bg-sunk px-4 py-3 text-sm text-ink">
      {message}
    </div>
  );
}
