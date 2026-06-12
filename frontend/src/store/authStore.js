import { create } from 'zustand';

if (typeof window !== 'undefined') {
  window.localStorage.removeItem('settlo-auth');
}

const useAuthStore = create((set) => ({
  user: null,
  accessToken: null,
  refreshToken: null,

  setAuth: ({ user, accessToken, refreshToken }) =>
    set({ user, accessToken, refreshToken }),

  setUser: (user) => set({ user }),

  setAccessToken: (accessToken) => set({ accessToken }),

  clearAuth: () => set({ user: null, accessToken: null, refreshToken: null }),
}));

export default useAuthStore;
