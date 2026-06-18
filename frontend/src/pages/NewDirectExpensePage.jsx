import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';
import useAuthStore from '../store/authStore';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import { SkeletonList } from '../components/LoadingSpinner';

export default function NewDirectExpensePage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  const [friends, setFriends] = useState([]);
  const [selected, setSelected] = useState({});
  const [title, setTitle] = useState('');
  const [amount, setAmount] = useState('');
  const [paidBy, setPaidBy] = useState(user?.id || '');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api
      .get('/friends')
      .then(({ data }) => setFriends(data))
      .catch((err) =>
        setError(err.response?.data?.detail || 'Failed to load friends')
      )
      .finally(() => setLoading(false));
  }, []);

  // Ensure paidBy is set once user is available
  useEffect(() => {
    if (!paidBy && user?.id) setPaidBy(user.id);
  }, [user, paidBy]);

  // Participants = me + selected friends.
  const participantIds = useMemo(() => {
    const ids = [user?.id].filter(Boolean);
    friends.forEach((f) => {
      if (selected[f.id]) ids.push(f.id);
    });
    return ids;
  }, [friends, selected, user]);

  const totalAmount = parseFloat(amount) || 0;

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    if (!title.trim()) {
      setError('Title is required');
      return;
    }
    if (!(totalAmount > 0)) {
      setError('Amount must be greater than 0');
      return;
    }
    if (participantIds.length < 2) {
      setError('Pick at least one friend');
      return;
    }
    setSubmitting(true);
    try {
      await api.post('/direct-expenses', {
        title: title.trim(),
        amount: totalAmount.toFixed(2),
        paid_by: paidBy,
        split_type: 'EQUAL',
        participant_ids: participantIds,
      });
      navigate('/friends');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add expense');
      setSubmitting(false);
    }
  };

  if (loading) return <SkeletonList count={3} />;

  const payerOptions = friends.filter((f) => selected[f.id]);

  return (
    <div className="space-y-4">
      <h1 className="text-[28px] font-semibold text-white">Friend Expense</h1>
      <form onSubmit={handleSubmit} className="glass space-y-4 p-6">
        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-white/50">
            Title
          </label>
          <input
            type="text"
            placeholder="e.g. Dinner"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={100}
            className="input-glass"
          />
        </div>

        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-white/50">
            Amount
          </label>
          <div className="relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-white/35">
              $
            </span>
            <input
              type="number"
              inputMode="decimal"
              min="0.01"
              step="0.01"
              placeholder="0.00"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="input-glass pl-8"
            />
          </div>
        </div>

        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-white/50">
            Split with
          </label>
          <div className="space-y-2 rounded-[14px] border border-white/10 bg-white/[0.04] p-4">
            {friends.length === 0 && (
              <p className="text-sm text-white/45">
                Add friends first to split with them.
              </p>
            )}
            {friends.map((f) => (
              <label
                key={f.id}
                className="flex cursor-pointer items-center gap-3 text-[15px] text-white/75"
              >
                <input
                  type="checkbox"
                  checked={!!selected[f.id]}
                  onChange={(e) => {
                    setSelected((prev) => ({ ...prev, [f.id]: e.target.checked }));
                    if (!e.target.checked && paidBy === f.id) setPaidBy(user?.id);
                  }}
                />
                {f.username || f.phone_number}
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-white/50">
            Paid by
          </label>
          <select
            value={paidBy}
            onChange={(e) => setPaidBy(e.target.value)}
            className="input-glass"
          >
            <option value={user?.id}>You</option>
            {payerOptions.map((f) => (
              <option key={f.id} value={f.id}>
                {f.username || f.phone_number}
              </option>
            ))}
          </select>
        </div>

        <ErrorMessage message={error} />
        <div className="flex gap-3">
          <Button
            type="button"
            variant="secondary"
            className="flex-1"
            onClick={() => navigate('/friends')}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="accent"
            disabled={submitting}
            className="flex-1"
          >
            {submitting ? 'Saving…' : 'Add Expense'}
          </Button>
        </div>
      </form>
    </div>
  );
}
