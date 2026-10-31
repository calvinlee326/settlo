import axios from 'axios';
import { mutate, unload } from 'swr';
import useAuthStore from '../store/authStore';

// Same origin everywhere: Vercel rewrites /api to the backend in production and
// Vite proxies it in development, so the refresh cookie is first-party (Safari
// blocks it cross-site) and requests skip CORS preflights.
const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const { accessToken } = useAuthStore.getState();
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

let refreshPromise = null;

// Each refresh retires the cookie it sends and sets a new one, and all tabs
// share that cookie. Tabs take turns so none sends a cookie another tab just
// retired, which would sign it out.
const postRefresh = () => axios.post('/api/auth/refresh', null, { withCredentials: true });

async function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = (
      navigator.locks ? navigator.locks.request('settlo-refresh', postRefresh) : postRefresh()
    ).then(({ data }) => {
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
  if (state.user?.id !== prev.user?.id) unload({ revalidate: false });
});

export default api;
