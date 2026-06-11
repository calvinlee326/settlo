import axios from 'axios';
import useAuthStore from '../store/authStore';

const API_BASE_URL =
  import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: { 'Content-Type': 'application/json' },
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
  const { refreshToken } = useAuthStore.getState();
  if (!refreshToken) throw new Error('No refresh token');
  const { data } = await axios.post(`${API_BASE_URL}/api/auth/refresh`, {
    refresh_token: refreshToken,
  });
  useAuthStore.getState().setAccessToken(data.access_token);
  return data.access_token;
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const isAuthRoute =
      original?.url?.includes('/auth/send-otp') ||
      original?.url?.includes('/auth/verify-otp') ||
      original?.url?.includes('/auth/refresh');

    if (
      error.response?.status === 401 &&
      !original._retry &&
      !isAuthRoute
    ) {
      original._retry = true;
      try {
        refreshPromise = refreshPromise || refreshAccessToken();
        const token = await refreshPromise;
        refreshPromise = null;
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      } catch (refreshError) {
        refreshPromise = null;
        useAuthStore.getState().clearAuth();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

export default api;
