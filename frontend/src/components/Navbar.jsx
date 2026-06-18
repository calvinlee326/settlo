import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../api/axios';
import useAuthStore from '../store/authStore';

export default function Navbar() {
  const { user, refreshToken, clearAuth } = useAuthStore();
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [requestCount, setRequestCount] = useState(0);
  const menuRef = useRef(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // Poll incoming friend requests so the badge updates when someone adds you.
  useEffect(() => {
    if (!user) return;
    let active = true;
    const fetchCount = () =>
      api
        .get('/friends/requests')
        .then(({ data }) => active && setRequestCount(data.length))
        .catch(() => {});
    fetchCount();
    const id = setInterval(fetchCount, 30000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [user]);

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
    setMenuOpen(false);
    try {
      await api.post('/auth/logout', { refresh_token: refreshToken });
    } catch {
      // Token may already be expired; clear local state regardless
    }
    clearAuth();
    navigate('/login');
  };

  return (
    <nav className={`navbar-glass ${scrolled ? 'scrolled' : ''}`}>
      <div className="mx-auto flex h-full max-w-[480px] items-center justify-between px-4">
        <Link
          to="/"
          className="text-lg font-semibold tracking-wide text-white"
        >
          Settlo
        </Link>
        <div className="flex items-center gap-4">
          <Link
            to="/friends"
            className="relative text-sm font-medium text-white/55 transition-colors hover:text-white"
          >
            Friends
            {requestCount > 0 && (
              <span className="absolute -right-3 -top-2 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold leading-none text-white shadow-[0_0_8px_rgba(239,68,68,0.5)]">
                {requestCount > 99 ? '99+' : requestCount}
              </span>
            )}
          </Link>
          {user && (
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setMenuOpen((open) => !open)}
                className="flex items-center gap-1 text-sm font-medium text-white/75 transition-colors hover:text-white"
              >
                {user.username || user.phone_number}
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
                <div className="glass absolute right-0 mt-2 w-40 overflow-hidden rounded-2xl py-1">
                  <button
                    onClick={() => {
                      setMenuOpen(false);
                      navigate('/settings');
                    }}
                    className="block w-full px-4 py-2.5 text-left text-sm text-white/80 transition-colors hover:bg-white/10"
                  >
                    Settings
                  </button>
                  <button
                    onClick={handleLogout}
                    className="block w-full px-4 py-2.5 text-left text-sm text-red-400 transition-colors hover:bg-white/10"
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
