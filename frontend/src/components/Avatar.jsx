// Ink wash has one chromatic note, so avatars vary by tone rather than hue.
const TONES = [
  { bg: '#6D8196', fg: '#FFFFE3' },
  { bg: '#4A4A4A', fg: '#FFFFE3' },
  { bg: '#5F7A5C', fg: '#FFFFE3' },
  { bg: '#9C5B4A', fg: '#FFFFE3' },
  { bg: '#CBCBCB', fg: '#4A4A4A' },
  { bg: '#55677A', fg: '#FFFFE3' },
  { bg: '#8E8E7A', fg: '#FFFFE3' },
  { bg: '#EAEEF2', fg: '#55677A' },
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
      className={`flex shrink-0 items-center justify-center rounded-full font-semibold ${sizeClass}`}
    >
      {initials}
    </div>
  );
}
