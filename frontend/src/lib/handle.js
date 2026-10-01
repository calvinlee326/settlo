// Mirrors HANDLE_PATTERN in backend/app/schemas/user.py.
const HANDLE_RE = /^(?=.*[a-z])(?!.*\.\.)[a-z0-9_][a-z0-9_.]{1,28}[a-z0-9_]$/;
const PHONE_INPUT_RE = /^\+?[\d\s().-]+$/;

export const HANDLE_RULES =
  '3-30 letters, numbers, underscores or periods, with at least one letter and no period at the start, at the end, or twice in a row';

export function normalizeHandle(value) {
  return value.trim().replace(/^@/, '').toLowerCase();
}

export function isValidHandle(handle) {
  return HANDLE_RE.test(handle);
}

// "909-555-0101" becomes a phone lookup; "ada" an ID lookup (a typed "@" is ignored). null if neither.
export function parseContact(input) {
  const value = input.trim();
  if (!value.startsWith('@') && PHONE_INPUT_RE.test(value)) {
    let digits = value.replace(/\D/g, '');
    if (digits.length === 11 && digits.startsWith('1')) digits = digits.slice(1);
    if (digits.length === 10) return { phone_number: `+1${digits}` };
  }
  const handle = normalizeHandle(value);
  return isValidHandle(handle) ? { handle } : null;
}
