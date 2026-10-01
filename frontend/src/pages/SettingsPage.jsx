import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../api/axios';
import useAuthStore from '../store/authStore';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import HandleInput from '../components/HandleInput';
import { HANDLE_RULES, isValidHandle, normalizeHandle } from '../lib/handle';
import { USER_GUIDE_URL } from '../lib/links';

export default function SettingsPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const [username, setUsername] = useState(user?.username || '');
  const [handle, setHandle] = useState(user?.handle || '');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSave = async (event) => {
    event.preventDefault();
    setError('');
    setNotice('');
    const id = normalizeHandle(handle);
    const handleChanged = id !== (user?.handle || '');
    if (!username.trim()) {
      setError('Enter your name');
      return;
    }
    if (handleChanged && !isValidHandle(id)) {
      setError(`Your ID must be ${HANDLE_RULES}.`);
      return;
    }
    setSaving(true);
    try {
      const { data } = await api.post('/auth/set-username', {
        username: username.trim(),
      });
      setUser(data);
      if (handleChanged) {
        const { data: updated } = await api.post('/auth/set-handle', { handle: id });
        setUser(updated);
      }
      setHandle(id);
      setNotice('Saved');
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save your profile.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-[28px] font-semibold text-ink">Settings</h1>
      <form onSubmit={handleSave} className="card space-y-4 p-6">
        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-muted">
            Name
          </label>
          <input
            type="text"
            placeholder="Enter your name"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            maxLength={50}
            className="input"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-muted">
            ID
          </label>
          <HandleInput
            value={handle}
            onChange={setHandle}
            currentHandle={user?.handle}
            hint={`Friends add you with this. ${HANDLE_RULES}.`}
          />
        </div>
        <ErrorMessage message={error} />
        {notice && <p className="text-sm text-ink">{notice}</p>}
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
      {user?.email && (
        <div className="card space-y-1 p-6">
          <h2 className="text-[13px] font-medium text-muted">Signed in with Google</h2>
          <p className="text-sm text-ink">{user.email}</p>
        </div>
      )}
      <p className="pt-2 text-center text-[13px] text-muted">
        <a
          href={USER_GUIDE_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-ink"
        >
          How to use
        </a>
        {' · '}
        <Link to="/privacy" className="underline hover:text-ink">
          Privacy Policy
        </Link>
      </p>
    </div>
  );
}
