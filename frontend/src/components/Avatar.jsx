const GRADIENTS = [
  ['#7c3aed', '#0ea5e9'],
  ['#0ea5e9', '#14b8a6'],
  ['#ec4899', '#8b5cf6'],
  ['#f59e0b', '#ef4444'],
  ['#14b8a6', '#22c55e'],
  ['#6366f1', '#ec4899'],
  ['#0ea5e9', '#6366f1'],
  ['#a855f7', '#f43f5e'],
];

function gradientFor(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash * 31 + name.charCodeAt(i)) | 0;
  }
  const [from, to] = GRADIENTS[Math.abs(hash) % GRADIENTS.length];
  return `linear-gradient(135deg, ${from}, ${to})`;
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
      style={{ background: gradientFor(display) }}
      className={`flex shrink-0 items-center justify-center rounded-full font-semibold text-white shadow-[0_2px_12px_rgba(0,0,0,0.3)] ring-1 ring-white/20 ${sizeClass}`}
    >
      {initials}
    </div>
  );
}
