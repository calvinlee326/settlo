import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api/axios';
import useAuthStore from '../store/authStore';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import LoadingSpinner from '../components/LoadingSpinner';

export default function NewExpensePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  const [members, setMembers] = useState([]);
  const [title, setTitle] = useState('');
  const [amount, setAmount] = useState('');
  const [paidBy, setPaidBy] = useState('');
  const [splitType, setSplitType] = useState('EQUAL');
  const [customSplits, setCustomSplits] = useState({});
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api
      .get(`/groups/${id}`)
      .then(({ data }) => {
        setMembers(data.members);
        setPaidBy(user?.id || data.members[0]?.id || '');
      })
      .catch((err) =>
        setError(err.response?.data?.detail || 'Failed to load group')
      )
      .finally(() => setLoading(false));
  }, [id, user]);

  const totalAmount = parseFloat(amount) || 0;
  const customTotal = useMemo(
    () =>
      members.reduce(
        (sum, m) => sum + (parseFloat(customSplits[m.id]) || 0),
        0
      ),
    [members, customSplits]
  );
  const customDiff = +(totalAmount - customTotal).toFixed(2);
  const customValid = totalAmount > 0 && Math.abs(customDiff) < 0.005;

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
    if (splitType === 'CUSTOM' && !customValid) {
      setError('Custom split amounts must add up to the total');
      return;
    }
    setSubmitting(true);
    try {
      const body = {
        title: title.trim(),
        amount: totalAmount.toFixed(2),
        paid_by: paidBy,
        split_type: splitType,
      };
      if (splitType === 'CUSTOM') {
        body.splits = members.map((m) => ({
          user_id: m.id,
          amount: (parseFloat(customSplits[m.id]) || 0).toFixed(2),
        }));
      }
      await api.post(`/groups/${id}/expenses/`, body);
      navigate(`/groups/${id}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add expense');
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-900">Add Expense</h1>
      <form
        onSubmit={handleSubmit}
        className="space-y-4 rounded-2xl bg-white p-6 shadow-sm"
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Title
          </label>
          <input
            type="text"
            placeholder="e.g. Dinner at Luigi's"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={100}
            className="w-full rounded-xl border border-slate-300 px-4 py-3 text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Amount
          </label>
          <div className="relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
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
              className="w-full rounded-xl border border-slate-300 py-3 pl-8 pr-4 text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100"
            />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Paid by
          </label>
          <select
            value={paidBy}
            onChange={(e) => setPaidBy(e.target.value)}
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100"
          >
            {members.map((m) => (
              <option key={m.id} value={m.id}>
                {m.id === user?.id
                  ? `${m.username || m.phone_number} (you)`
                  : m.username || m.phone_number}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Split type
          </label>
          <div className="grid grid-cols-2 gap-2">
            {['EQUAL', 'CUSTOM'].map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => setSplitType(type)}
                className={`rounded-xl border px-4 py-2.5 text-sm font-semibold transition ${
                  splitType === type
                    ? 'border-primary-600 bg-primary-50 text-primary-700'
                    : 'border-slate-300 bg-white text-slate-600 hover:bg-slate-50'
                }`}
              >
                {type === 'EQUAL' ? 'Equal' : 'Custom'}
              </button>
            ))}
          </div>
        </div>

        {splitType === 'CUSTOM' && (
          <div className="space-y-2 rounded-xl bg-slate-50 p-4">
            {members.map((m) => (
              <div key={m.id} className="flex items-center gap-3">
                <span className="flex-1 truncate text-sm text-slate-700">
                  {m.id === user?.id
                    ? 'You'
                    : m.username || m.phone_number}
                </span>
                <div className="relative w-28">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-slate-400">
                    $
                  </span>
                  <input
                    type="number"
                    inputMode="decimal"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    value={customSplits[m.id] ?? ''}
                    onChange={(e) =>
                      setCustomSplits((prev) => ({
                        ...prev,
                        [m.id]: e.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-slate-300 py-2 pl-7 pr-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none"
                  />
                </div>
              </div>
            ))}
            <div
              className={`pt-2 text-right text-sm font-semibold ${
                customValid ? 'text-emerald-600' : 'text-red-600'
              }`}
            >
              {customValid
                ? `Adds up to $${totalAmount.toFixed(2)}`
                : customDiff > 0
                  ? `$${customDiff.toFixed(2)} left to assign`
                  : `$${Math.abs(customDiff).toFixed(2)} over the total`}
            </div>
          </div>
        )}

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
            disabled={submitting || (splitType === 'CUSTOM' && !customValid)}
            className="flex-1"
          >
            {submitting ? 'Saving…' : 'Add Expense'}
          </Button>
        </div>
      </form>
    </div>
  );
}
