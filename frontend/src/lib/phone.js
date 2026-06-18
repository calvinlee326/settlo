export function formatPhone(value) {
  let d = value.replace(/\D/g, '');
  if (d.length === 11 && d.startsWith('1')) d = d.slice(1);
  d = d.slice(0, 10);
  const parts = [d.slice(0, 3), d.slice(3, 6), d.slice(6, 10)].filter(Boolean);
  return parts.join('-');
}
