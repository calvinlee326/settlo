import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import api from '../api/axios';
import useAuthStore, { useIsAuthenticated } from '../store/authStore';
import ErrorMessage from '../components/ErrorMessage';
import GoogleButton, { isGoogleEnabled } from '../components/GoogleButton';

export default function LoginPage() {
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const isAuthenticated = useIsAuthenticated();
  const setAuth = useAuthStore((s) => s.setAuth);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const handleGoogle = async (credential) => {
    setError('');
    try {
      const { data } = await api.post('/auth/google', { credential });
      setAuth({ user: data.user, accessToken: data.access_token });
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || 'Google sign-in failed. Try again.');
    }
  };

  return (
    <div className="page-enter flex min-h-screen items-center justify-center px-4">
      <div className="card w-full max-w-md p-8">
        <h1 className="text-center text-[28px] font-semibold text-ink">
          Settlo
        </h1>
        <p className="mt-2 text-center text-[15px] text-muted">
          Split bills with friends. Settle up in fewer payments.
        </p>
        <div className="mt-8 space-y-4">
          {isGoogleEnabled ? (
            <GoogleButton onCredential={handleGoogle} />
          ) : (
            <ErrorMessage message="Google sign-in is not configured. Set VITE_GOOGLE_CLIENT_ID." />
          )}
          <ErrorMessage message={error} />
        </div>
        <p className="mt-4 text-center text-[13px] text-muted">
          New here? An account is created automatically on first login.
        </p>
        <p className="mt-6 text-center text-[13px]">
          <Link to="/privacy" className="text-muted underline hover:text-ink">
            Privacy Policy
          </Link>
        </p>
      </div>
    </div>
  );
}
