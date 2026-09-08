import axios from 'axios';
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
      return data.access_token;
    }).finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

export async function initializeSession() {
  useAuthStore.getState().setSessionStatus('loading');
  try {
    await refreshAccessToken();
    const { data } = await api.get('/auth/me', { _retry: true });
    useAuthStore.getState().setUser(data);
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
  (response) => response,
  async (error) => {
    const original = error.config;
    const isAuthRoute =
      original?.url?.includes('/auth/send-otp') ||
      original?.url?.includes('/auth/verify-otp') ||
      original?.url?.includes('/auth/refresh') ||
      original?.url?.includes('/auth/logout');

    if (
      error.response?.status === 401 &&
      original && !original._retry &&
      !isAuthRoute
    ) {
      original._retry = true;
      try {
        const token = await refreshAccessToken();
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

export default api;
