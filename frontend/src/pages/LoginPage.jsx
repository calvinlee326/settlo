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

  return (
    <div className="page-enter flex min-h-screen items-center justify-center px-4">
      <div className="glass-strong w-full max-w-md p-8">
        <h1 className="text-center text-[28px] font-semibold text-white">
          Settlo
        </h1>
        <p className="mt-2 text-center text-[15px] text-white/55">
          Split bills with friends. Settle up in fewer payments.
        </p>
        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          <div>
            <label
              htmlFor="phone"
              className="mb-1.5 block text-[13px] font-medium text-white/50"
            >
              Phone number (US)
            </label>
            <input
              id="phone"
              type="tel"
              autoComplete="tel"
              placeholder="(909) 555-0101"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="input-glass"
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
        <p className="mt-4 text-center text-[13px] text-white/30">
          New here? An account is created automatically on first login.
        </p>
      </div>
    </div>
  );
}
