import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';

export default function LoginPage() {
  const [phone, setPhone] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    const normalized = phone.replace(/[\s-]/g, '');
    if (!/^\+?[0-9]{7,15}$/.test(normalized)) {
      setError('Enter a valid phone number, e.g. +1234567890');
      return;
    }
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

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-md rounded-3xl bg-white p-8 shadow-sm">
        <h1 className="text-center text-3xl font-bold text-primary-600">
          Settlo
        </h1>
        <p className="mt-2 text-center text-sm text-slate-500">
          Split bills with friends. Settle up in fewer payments.
        </p>
        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          <div>
            <label
              htmlFor="phone"
              className="mb-1 block text-sm font-medium text-slate-700"
            >
              Phone number
            </label>
            <input
              id="phone"
              type="tel"
              autoComplete="tel"
              placeholder="+1234567890"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full rounded-xl border border-slate-300 px-4 py-3 text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100"
            />
          </div>
          <ErrorMessage message={error} />
          <Button type="submit" disabled={loading} className="w-full py-3">
            {loading ? 'Sending…' : 'Send verification code'}
          </Button>
        </form>
        <p className="mt-4 text-center text-xs text-slate-400">
          New here? An account is created automatically on first login.
        </p>
      </div>
    </div>
  );
}
