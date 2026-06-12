import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import api from '../api/axios';
import useAuthStore, { useIsAuthenticated } from '../store/authStore';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import OtpInput from '../components/OtpInput';

export default function VerifyPage() {
  const [code, setCode] = useState('');
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);
  const setUser = useAuthStore((s) => s.setUser);
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useIsAuthenticated();
  // Derived from the persisted user so a reload mid-onboarding keeps the
  // username step instead of bouncing a half-onboarded user to home.
  const needsUsername = isAuthenticated && user && !user.username;

  const phone = sessionStorage.getItem('settlo-phone');

  const handleVerify = async (event) => {
    event.preventDefault();
    if (code.length !== 6) {
      setError('Enter the 6-digit code');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const { data } = await api.post('/auth/verify-otp', {
        phone_number: phone,
        code,
      });
      setAuth({
        user: data.user,
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
      });
      if (!data.is_new_user) {
        sessionStorage.removeItem('settlo-phone');
        navigate('/', { replace: true });
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Verification failed. Try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSetUsername = async (event) => {
    event.preventDefault();
    if (!username.trim()) {
      setError('Enter your name');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const { data } = await api.post('/auth/set-username', {
        username: username.trim(),
      });
      setUser(data);
      sessionStorage.removeItem('settlo-phone');
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save your name.');
    } finally {
      setLoading(false);
    }
  };

  if (isAuthenticated && !needsUsername) {
    return <Navigate to="/" replace />;
  }

  if (!phone && !isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="page-enter flex min-h-screen items-center justify-center px-4">
      <div className="glass-strong w-full max-w-md p-8">
        {!needsUsername ? (
          <>
            <h1 className="text-center text-[28px] font-semibold text-white">
              Enter verification code
            </h1>
            <p className="mt-2 text-center text-[15px] text-white/55">
              We sent a 6-digit code to{' '}
              <span className="font-medium text-white/90">{phone}</span>.
              <br />
              <span className="text-[13px] text-white/30">
                (Dev mode: check the backend terminal.)
              </span>
            </p>
            <form onSubmit={handleVerify} className="mt-8 space-y-4">
              <OtpInput value={code} onChange={setCode} />
              <ErrorMessage message={error} />
              <Button
                type="submit"
                variant="accent"
                disabled={loading}
                className="w-full"
              >
                {loading ? 'Verifying…' : 'Verify'}
              </Button>
            </form>
            <button
              onClick={() => navigate('/login')}
              className="mt-4 w-full text-center text-sm text-sky-400 transition-colors hover:text-sky-300"
            >
              Use a different number
            </button>
          </>
        ) : (
          <>
            <h1 className="text-center text-[28px] font-semibold text-white">
              Welcome to Settlo!
            </h1>
            <p className="mt-2 text-center text-[15px] text-white/55">
              What should your friends call you?
            </p>
            <form onSubmit={handleSetUsername} className="mt-8 space-y-4">
              <input
                type="text"
                placeholder="Enter your name"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                maxLength={50}
                autoFocus
                className="input-glass"
              />
              <ErrorMessage message={error} />
              <Button
                type="submit"
                variant="accent"
                disabled={loading}
                className="w-full"
              >
                {loading ? 'Saving…' : 'Continue'}
              </Button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
