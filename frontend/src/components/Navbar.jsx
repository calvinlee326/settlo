import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import useSWR from 'swr';
import api from '../api/axios';
import useAuthStore from '../store/authStore';

export default function Navbar() {
  const { user, clearAuth } = useAuthStore();
  const navigate = useNavigate();
  const [logoutError, setLogoutError] = useState('');
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);
  // Poll incoming friend requests and group invites so the badges update when
  // someone adds you. HomePage reads the same invites key, so it is fetched once.
  const { data: requests } = useSWR(user ? '/friends/requests' : null, { refreshInterval: 30000 });
  const { data: invites } = useSWR(user ? '/group-invitations' : null, { refreshInterval: 30000 });
  const requestCount = requests?.length ?? 0;
  const inviteCount = invites?.length ?? 0;
  // Warm the main lists on hover/touch of a nav link so the next screen opens from cache.
  const [warm, setWarm] = useState(false);
  useSWR(warm ? '/groups/' : null);
  useSWR(warm ? '/friends' : null);
  const warmLists = () => setWarm(true);
  const coolLists = () => setWarm(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const onClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [menuOpen]);

  const handleLogout = async () => {
    setLogoutError('');
    try {
      await api.post('/auth/logout');
    } catch {
      setLogoutError('Logout failed. Please try again.');
      return;
    }
    setMenuOpen(false);
    clearAuth();
    navigate('/login');
  };

  return (
    <nav className={`navbar ${scrolled ? 'scrolled' : ''}`}>
      <div className="mx-auto flex h-full max-w-[480px] items-center justify-between px-4">
        <Link
          to="/"
          onPointerEnter={warmLists}
          onPointerLeave={coolLists}
          className="relative text-lg font-semibold tracking-tight text-ink"
        >
          Settlo
          {inviteCount > 0 && (
            <span className="absolute -right-3 -top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-ink px-1 text-[10px] font-bold leading-none text-white">
              {inviteCount > 99 ? '99+' : inviteCount}
            </span>
          )}
        </Link>
        <div className="flex items-center gap-4">
          <Link
            to="/friends"
            onPointerEnter={warmLists}
            onPointerLeave={coolLists}
            className="relative text-sm font-medium text-muted transition-colors hover:text-ink"
          >
            Friends
            {requestCount > 0 && (
              <span className="absolute -right-3 -top-2 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-ink px-1 text-[10px] font-bold leading-none text-white">
                {requestCount > 99 ? '99+' : requestCount}
              </span>
            )}
          </Link>
          {user && (
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setMenuOpen((open) => !open)}
                className="flex items-center gap-1 text-sm font-medium text-ink-soft transition-colors hover:text-ink"
              >
                {user.username || user.handle}
                <svg
                  className={`h-3 w-3 transition-transform ${menuOpen ? 'rotate-180' : ''}`}
                  viewBox="0 0 12 12"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                >
                  <path d="M3 4.5 6 7.5 9 4.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              {menuOpen && (
                <div className="card absolute right-0 mt-2 w-40 overflow-hidden py-1">
                  <button
                    onPointerEnter={warmLists}
                    onPointerLeave={coolLists}
                    onClick={() => {
                      setMenuOpen(false);
                      navigate('/history');
                    }}
                    className="block w-full px-4 py-2.5 text-left text-sm text-ink-soft transition-colors hover:bg-sunk"
                  >
                    Payment History
                  </button>
                  <button
                    onClick={() => {
                      setMenuOpen(false);
                      navigate('/settings');
                    }}
                    className="block w-full px-4 py-2.5 text-left text-sm text-ink-soft transition-colors hover:bg-sunk"
                  >
                    Settings
                  </button>
                  {logoutError && <p role="alert" className="px-4 py-2 text-sm">{logoutError}</p>}
                  <button
                    onClick={handleLogout}
                    className="block w-full px-4 py-2.5 text-left text-sm text-ink transition-colors hover:bg-sunk"
                  >
                    Logout
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
