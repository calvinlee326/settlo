export default function ErrorMessage({ message }) {
  if (!message) return null;
  return (
    <div className="rounded-card border border-clay/35 bg-clay-tint px-4 py-3 text-sm text-clay">
      {message}
    </div>
  );
}
