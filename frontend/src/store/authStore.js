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

      clearAuth: () =>
        set({ user: null, accessToken: null, refreshToken: null }),
    }),
    { name: 'settlo-auth' }
  )
);

export default useAuthStore;
