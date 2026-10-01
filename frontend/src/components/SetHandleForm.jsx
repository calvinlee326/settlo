import { useState } from 'react';
import api from '../api/axios';
import useAuthStore from '../store/authStore';
import Button from './Button';
import ErrorMessage from './ErrorMessage';
import HandleInput from './HandleInput';
import { HANDLE_RULES, isValidHandle, normalizeHandle } from '../lib/handle';

export default function SetHandleForm() {
  const setUser = useAuthStore((s) => s.setUser);
  const [handle, setHandle] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const save = async (event) => {
    event.preventDefault();
    const id = normalizeHandle(handle);
    if (!isValidHandle(id)) {
      setError(`Your ID must be ${HANDLE_RULES}.`);
      return;
    }
    setError('');
    setSaving(true);
    try {
      const { data } = await api.post('/auth/set-handle', { handle: id });
      setUser(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save your ID.');
      setSaving(false);
    }
  };

  return (
    <form onSubmit={save} className="space-y-2 text-left">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <HandleInput
            value={handle}
            onChange={setHandle}
            hint="You can change it later in Settings."
          />
        </div>
        <Button type="submit" variant="accent" disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
      </div>
      <ErrorMessage message={error} />
    </form>
  );
}
