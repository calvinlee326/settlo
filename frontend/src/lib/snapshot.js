// The last signed-in user and the data their screens loaded, so the app opens
// on them at once and refreshes in the background instead of waiting on the
// network. Tokens are never stored here.
const KEY = 'settlo-snapshot';
// Another build may expect differently shaped data, so only reuse our own.
const BUILD = import.meta.url;

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY));
    if (saved?.build === BUILD && saved.user?.id && saved.data?.constructor === Object) return saved;
  } catch {
    // Unreadable snapshot: open as if there were none.
  }
  return { user: null, data: {} };
}

const saved = load();

export const savedUser = saved.user;
// SWR's fallback: screens render this until their own fetch returns.
export const savedData = saved.data;

export function saveSnapshot(user, cache) {
  if (!user) return;
  const data = {};
  for (const key of cache.keys()) {
    const value = cache.get(key)?.data;
    if (key.startsWith('/') && value !== undefined) data[key] = value;
  }
  try {
    localStorage.setItem(KEY, JSON.stringify({ build: BUILD, user, data }));
  } catch {
    // ponytail: storage full keeps the last snapshot that fit; cap what is saved if this ever happens.
  }
}

// On an account change. SWR holds on to the fallback object, so empty it in place.
export function clearSnapshot(signedOut) {
  for (const key of Object.keys(savedData)) delete savedData[key];
  if (signedOut) localStorage.removeItem(KEY);
}

export function onSnapshotRemoved(fn) {
  window.addEventListener('storage', (e) => {
    if (e.key === KEY && e.newValue === null) fn();
  });
}
