// Greyscale ramp between the two source values, so avatars stay distinguishable
// without introducing hue. Text colour is picked per step to stay legible.
const TONES = [
  { bg: '#4A4A4A', fg: '#FFFFFF' },
  { bg: '#8A8A8A', fg: '#FFFFFF' },
  { bg: '#CBCBCB', fg: '#4A4A4A' },
  { bg: '#6A6A6A', fg: '#FFFFFF' },
  { bg: '#A8A8A8', fg: '#FFFFFF' },
  { bg: '#E5E5E5', fg: '#4A4A4A' },
];

function toneFor(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash * 31 + name.charCodeAt(i)) | 0;
  }
  return TONES[Math.abs(hash) % TONES.length];
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
  const tone = toneFor(display);

  return (
    <div
      title={display}
      style={{ background: tone.bg, color: tone.fg }}
      className={`flex shrink-0 items-center justify-center rounded-full font-semibold ring-1 ring-rule ${sizeClass}`}
    >
      {initials}
    </div>
  );
}
