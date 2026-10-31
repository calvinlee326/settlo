import { create } from 'zustand';
import { savedUser } from '../lib/snapshot';

localStorage.removeItem('settlo-auth');

const useAuthStore = create((set) => ({
  user: savedUser,
  accessToken: null,
  sessionStatus: 'loading',
  setAuth: ({ user, accessToken }) => set({ user, accessToken, sessionStatus: 'ready' }),
  setUser: (user) => set({ user }),
  setAccessToken: (accessToken) => set({ accessToken }),
  setSessionStatus: (sessionStatus) => set({ sessionStatus }),
  clearAuth: () => set({ user: null, accessToken: null, sessionStatus: 'ready' }),
}));

// A saved user counts before the session is restored, so a returning user opens
// on their screens. A restore rejected with 401 clears the user and sends them to login.
export const useIsAuthenticated = () =>
  useAuthStore((s) => Boolean(s.user));

export default useAuthStore;
