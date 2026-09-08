import { create } from 'zustand';

localStorage.removeItem('settlo-auth');

const useAuthStore = create((set) => ({
  user: null,
  accessToken: null,
  sessionStatus: 'loading',
  setAuth: ({ user, accessToken }) => set({ user, accessToken, sessionStatus: 'ready' }),
  setUser: (user) => set({ user }),
  setAccessToken: (accessToken) => set({ accessToken }),
  setSessionStatus: (sessionStatus) => set({ sessionStatus }),
  clearAuth: () => set({ user: null, accessToken: null, sessionStatus: 'ready' }),
}));

export const useIsAuthenticated = () =>
  useAuthStore((s) => Boolean(s.accessToken));

export default useAuthStore;
