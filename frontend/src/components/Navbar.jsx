import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../api/axios';
import useAuthStore from '../store/authStore';
import Avatar from './Avatar';

export default function Navbar() {
  const { user, refreshToken, clearAuth } = useAuthStore();
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleLogout = async () => {
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
        <div className="flex items-center gap-3">
          {user && (
            <div className="flex items-center gap-2">
              <Avatar name={user.username || user.phone_number} size="sm" />
              <span className="text-sm font-medium text-white/75">
                {user.username || user.phone_number}
              </span>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="text-sm font-medium text-white/55 transition-colors hover:text-red-400"
          >
            Logout
          </button>
        </div>
      </div>
    </nav>
  );
}
