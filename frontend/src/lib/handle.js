// Mirrors HANDLE_PATTERN in backend/app/schemas/user.py.
const HANDLE_RE = /^(?=.*[a-z])(?!.*\.\.)[a-z0-9_][a-z0-9_.]{1,28}[a-z0-9_]$/;

export const HANDLE_RULES =
  '3-30 letters, numbers, underscores or periods, with at least one letter and no period at the start, at the end, or twice in a row';

export function normalizeHandle(value) {
  return value.trim().replace(/^@/, '').toLowerCase();
}

export function isValidHandle(handle) {
  return HANDLE_RE.test(handle);
}
