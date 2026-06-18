import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';
import useAuthStore from '../store/authStore';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';

export default function SettingsPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const [username, setUsername] = useState(user?.username || '');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSave = async (event) => {
    event.preventDefault();
    setError('');
    setNotice('');
    if (!username.trim()) {
      setError('Enter your name');
      return;
    }
    setSaving(true);
    try {
      const { data } = await api.post('/auth/set-username', {
        username: username.trim(),
      });
      setUser(data);
      setNotice('Saved');
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save your name.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-[28px] font-semibold text-white">Settings</h1>
      <form onSubmit={handleSave} className="glass space-y-4 p-6">
        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-white/50">
            Name
          </label>
          <input
            type="text"
            placeholder="Enter your name"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            maxLength={50}
            className="input-glass"
          />
        </div>
        <ErrorMessage message={error} />
        {notice && <p className="text-sm text-emerald-400">{notice}</p>}
        <div className="flex gap-3">
          <Button
            type="button"
            variant="secondary"
            className="flex-1"
            onClick={() => navigate(-1)}
          >
            Back
          </Button>
          <Button
            type="submit"
            variant="accent"
            disabled={saving}
            className="flex-1"
          >
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </form>
    </div>
  );
}
