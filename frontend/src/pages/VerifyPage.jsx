import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';
import useAuthStore from '../store/authStore';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import OtpInput from '../components/OtpInput';

export default function VerifyPage() {
  const [code, setCode] = useState('');
  const [username, setUsername] = useState('');
  const [needsUsername, setNeedsUsername] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);
  const setUser = useAuthStore((s) => s.setUser);

  const phone = sessionStorage.getItem('settlo-phone');

  useEffect(() => {
    if (!phone) navigate('/login');
  }, [phone, navigate]);

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
      if (data.is_new_user) {
        setNeedsUsername(true);
      } else {
        sessionStorage.removeItem('settlo-phone');
        navigate('/');
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
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save your name.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-md rounded-3xl bg-white p-8 shadow-sm">
        {!needsUsername ? (
          <>
            <h1 className="text-center text-2xl font-bold text-slate-900">
              Enter verification code
            </h1>
            <p className="mt-2 text-center text-sm text-slate-500">
              We sent a 6-digit code to{' '}
              <span className="font-medium text-slate-700">{phone}</span>.
              <br />
              (Dev mode: check the backend terminal.)
            </p>
            <form onSubmit={handleVerify} className="mt-8 space-y-4">
              <OtpInput value={code} onChange={setCode} />
              <ErrorMessage message={error} />
              <Button type="submit" disabled={loading} className="w-full py-3">
                {loading ? 'Verifying…' : 'Verify'}
              </Button>
            </form>
            <button
              onClick={() => navigate('/login')}
              className="mt-4 w-full text-center text-sm text-primary-600 hover:underline"
            >
              Use a different number
            </button>
          </>
        ) : (
          <>
            <h1 className="text-center text-2xl font-bold text-slate-900">
              Welcome to Settlo!
            </h1>
            <p className="mt-2 text-center text-sm text-slate-500">
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
                className="w-full rounded-xl border border-slate-300 px-4 py-3 text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100"
              />
              <ErrorMessage message={error} />
              <Button type="submit" disabled={loading} className="w-full py-3">
                {loading ? 'Saving…' : 'Continue'}
              </Button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
