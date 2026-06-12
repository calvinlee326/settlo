export default function ErrorMessage({ message }) {
  if (!message) return null;
  return (
    <div className="rounded-2xl border border-red-400/40 bg-red-500/15 px-4 py-3 text-sm text-red-200 backdrop-blur-glass">
      {message}
    </div>
  );
}
