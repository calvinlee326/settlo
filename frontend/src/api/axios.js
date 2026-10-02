import axios from 'axios';
import { mutate, unload } from 'swr';
import useAuthStore from '../store/authStore';

const API_BASE_URL =
  import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
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

async function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = axios.post(`${API_BASE_URL}/api/auth/refresh`, null, {
      withCredentials: true,
    }).then(({ data }) => {
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
    // A write can move balances on any screen: drop every cached read so the
    // next screen fetches fresh, and refetch the ones on show (keepPreviousData
    // keeps them on screen meanwhile). Auth writes are skipped: logout must not
    // refetch, and an account switch is handled below.
    if (method !== 'get' && !url.startsWith('/auth/')) {
      mutate(() => true, undefined, { revalidate: true });
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
