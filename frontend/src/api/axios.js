import axios from 'axios';
import { mutate, unload } from 'swr';
import useAuthStore from '../store/authStore';
import { clearSnapshot, onSnapshotRemoved } from '../lib/snapshot';

// Same origin everywhere: Vercel rewrites /api to the backend in production and
// Vite proxies it in development, so the refresh cookie is first-party (Safari
// blocks it cross-site) and requests skip CORS preflights.
const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

api.interceptors.request.use(async (config) => {
  // The app opens on saved data before the session is restored. Wait for the
  // restore instead of sending a request that can only come back 401; if it
  // fails, the request goes anyway and the 401 path below handles it. Auth
  // routes skip the wait: logout runs inside the session lock, which a
  // refresh may be queued on.
  if (refreshPromise && !useAuthStore.getState().accessToken && !config.url.startsWith('/auth/')) {
    await refreshPromise.catch(() => {});
  }
  const { accessToken } = useAuthStore.getState();
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

let refreshPromise = null;

// Each refresh retires the cookie it sends and sets a new one, and all tabs
// share that cookie. Refreshes and logout take turns across tabs: otherwise a
// tab sends a cookie another tab just retired and is signed out, or a refresh
// landing after a logout sets a live cookie again. Never nest: locks are not
// reentrant, which is why the logout 401 path skips refresh.
export const withSessionLock = (fn) =>
  navigator.locks ? navigator.locks.request('settlo-session', fn) : fn();

const postRefresh = () => axios.post('/api/auth/refresh', null, { withCredentials: true });

async function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = withSessionLock(postRefresh).then(({ data }) => {
      useAuthStore.getState().setAccessToken(data.access_token);
      return data;
    }).finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

export async function initializeSession() {
  useAuthStore.getState().setSessionStatus('loading');
  try {
    const { user } = await refreshAccessToken();
    useAuthStore.getState().setUser(user);
    useAuthStore.getState().setSessionStatus('ready');
  } catch (error) {
    if (error.response?.status === 401) {
      useAuthStore.getState().clearAuth();
    } else {
      useAuthStore.getState().setSessionStatus('error');
    }
  }
}

api.interceptors.response.use(
  (response) => {
    const { method, url } = response.config;
    // A write can move balances on any screen: refetch the reads on show and
    // mark the rest to refetch when next shown. Cached data stays on screen
    // meanwhile, so the next page renders at once instead of a skeleton. Rates
    // never change on a write. Auth writes are skipped: logout must not
    // refetch, and an account switch is handled below.
    if (method !== 'get' && !url.startsWith('/auth/')) {
      mutate((key) => key !== '/rates');
    }
    return response;
  },
  async (error) => {
    const original = error.config;
    const isAuthRoute =
      original?.url?.endsWith('/auth/google') ||
      original?.url?.includes('/auth/refresh') ||
      original?.url?.includes('/auth/logout');

    if (
      error.response?.status === 401 &&
      original && !original._retry &&
      !isAuthRoute
    ) {
      original._retry = true;
      try {
        const { access_token: token } = await refreshAccessToken();
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      } catch (refreshError) {
        if (refreshError.response?.status === 401) {
          useAuthStore.getState().clearAuth();
        }
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

export const fetcher = (url) => api.get(url).then(({ data }) => data);

// Never let one account's cached reads reach the next one on this tab.
useAuthStore.subscribe((state, prev) => {
  if (state.user?.id !== prev.user?.id) {
    unload({ revalidate: false });
    clearSnapshot(!state.user);
  }
});

// Signing out in another tab removes the snapshot. Sign this tab out too, or
// its next save would put the old account's data back on the device.
onSnapshotRemoved(() => useAuthStore.getState().clearAuth());

export default api;
