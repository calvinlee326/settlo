import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import api from '../api/axios';
import useAuthStore, { useIsAuthenticated } from '../store/authStore';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import GoogleButton, { isGoogleEnabled } from '../components/GoogleButton';
import { formatPhone } from '../lib/phone';

export default function LoginPage() {
  const [phone, setPhone] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const isAuthenticated = useIsAuthenticated();
  const setAuth = useAuthStore((s) => s.setAuth);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    let digits = phone.replace(/\D/g, '');
    if (digits.length === 11 && digits.startsWith('1')) {
      digits = digits.slice(1);
    }
    if (digits.length !== 10) {
      setError('Enter a valid 10-digit US phone number');
      return;
    }
    const normalized = `+1${digits}`;
    setLoading(true);
    try {
      await api.post('/auth/send-otp', { phone_number: normalized });
      sessionStorage.setItem('settlo-phone', normalized);
      navigate('/verify');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to send OTP. Try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async (credential) => {
    setError('');
    try {
      const { data } = await api.post('/auth/google', { credential });
      setAuth({ user: data.user, accessToken: data.access_token });
      navigate(data.is_new_user ? '/verify' : '/', { replace: true });
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
        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          <div>
            <label
              htmlFor="phone"
              className="mb-1.5 block text-[13px] font-medium text-muted"
            >
              Phone number (US)
            </label>
            <input
              id="phone"
              type="tel"
              inputMode="numeric"
              autoComplete="tel"
              placeholder="909-555-0101"
              value={phone}
              onChange={(e) => setPhone(formatPhone(e.target.value))}
              className="input"
            />
          </div>
          <ErrorMessage message={error} />
          <Button
            type="submit"
            variant="accent"
            disabled={loading}
            className="w-full"
          >
            {loading ? 'Sending…' : 'Send verification code'}
          </Button>
        </form>
        <p className="mt-4 text-center text-[13px] text-muted">
          New here? An account is created automatically on first login.
        </p>
        {isGoogleEnabled && (
          <div className="mt-6 space-y-3 border-t border-rule pt-6">
            <GoogleButton onCredential={handleGoogle} />
            <p className="text-center text-[13px] text-muted">
              Already use Settlo with your phone? Sign in with your phone first,
              then link Google in Settings to keep your groups.
            </p>
          </div>
        )}
        <p className="mt-6 text-center text-[13px]">
          <Link to="/privacy" className="text-muted underline hover:text-ink">
            Privacy Policy
          </Link>
        </p>
      </div>
    </div>
  );
}
