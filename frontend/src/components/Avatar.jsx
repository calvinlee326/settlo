const COLORS = [
  'bg-indigo-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-rose-500',
  'bg-sky-500',
  'bg-violet-500',
  'bg-teal-500',
  'bg-orange-500',
];

function colorFor(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash * 31 + name.charCodeAt(i)) | 0;
  }
  return COLORS[Math.abs(hash) % COLORS.length];
}

export default function Avatar({ name, size = 'md' }) {
  const display = name || '?';
  const initials = display
    .split(/\s+/)
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
  const sizeClass =
    size === 'sm' ? 'h-8 w-8 text-xs' : size === 'lg' ? 'h-12 w-12 text-base' : 'h-10 w-10 text-sm';

  return (
    <div
      title={display}
      className={`flex items-center justify-center rounded-full font-semibold text-white ${sizeClass} ${colorFor(display)}`}
    >
      {initials}
    </div>
  );
}
