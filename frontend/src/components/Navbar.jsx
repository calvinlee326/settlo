import { Link, useNavigate } from 'react-router-dom';
import api from '../api/axios';
import useAuthStore from '../store/authStore';
import Avatar from './Avatar';

export default function Navbar() {
  const { user, refreshToken, clearAuth } = useAuthStore();
  const navigate = useNavigate();

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
    <nav className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-md items-center justify-between px-4 py-3">
        <Link to="/" className="text-xl font-bold text-primary-600">
          Settlo
        </Link>
        <div className="flex items-center gap-3">
          {user && (
            <div className="flex items-center gap-2">
              <Avatar name={user.username || user.phone_number} size="sm" />
              <span className="text-sm font-medium text-slate-700">
                {user.username || user.phone_number}
              </span>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="text-sm font-medium text-slate-500 hover:text-red-600"
          >
            Logout
          </button>
        </div>
      </div>
    </nav>
  );
}
