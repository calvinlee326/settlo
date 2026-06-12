import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';

export default function NewGroupPage() {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!name.trim()) {
      setError('Group name is required');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const { data } = await api.post('/groups/', {
        name: name.trim(),
        description: description.trim() || null,
      });
      navigate(`/groups/${data.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create group');
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-[28px] font-semibold text-white">New Group</h1>
      <form onSubmit={handleSubmit} className="glass space-y-4 p-6">
        <div>
          <label
            htmlFor="name"
            className="mb-1.5 block text-[13px] font-medium text-white/50"
          >
            Group name
          </label>
          <input
            id="name"
            type="text"
            placeholder="e.g. Tokyo Trip"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={100}
            className="input-glass"
          />
        </div>
        <div>
          <label
            htmlFor="description"
            className="mb-1.5 block text-[13px] font-medium text-white/50"
          >
            Description <span className="text-white/30">(optional)</span>
          </label>
          <textarea
            id="description"
            rows={3}
            placeholder="What is this group for?"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={255}
            className="input-glass resize-none"
          />
        </div>
        <ErrorMessage message={error} />
        <div className="flex gap-3">
          <Button
            type="button"
            variant="secondary"
            className="flex-1"
            onClick={() => navigate(-1)}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="accent"
            disabled={loading}
            className="flex-1"
          >
            {loading ? 'Creating…' : 'Create Group'}
          </Button>
        </div>
      </form>
    </div>
  );
}
