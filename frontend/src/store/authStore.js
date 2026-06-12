import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const useAuthStore = create(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,

      setAuth: ({ user, accessToken, refreshToken }) =>
        set({ user, accessToken, refreshToken }),

      setUser: (user) => set({ user }),

      setAccessToken: (accessToken) => set({ accessToken }),

      clearAuth: () => set({ user: null, accessToken: null, refreshToken: null }),
    }),
    {
      name: 'settlo-auth',
      // Keep the short-lived access token in memory only; it is re-minted
      // from the refresh token by the axios 401 interceptor after a reload.
      partialize: (state) => ({
        user: state.user,
        refreshToken: state.refreshToken,
      }),
    }
  )
);

export const useIsAuthenticated = () =>
  useAuthStore((s) => Boolean(s.accessToken || s.refreshToken));

export default useAuthStore;
