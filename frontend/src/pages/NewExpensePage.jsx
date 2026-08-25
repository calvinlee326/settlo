import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api/axios';
import useAuthStore from '../store/authStore';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import { SkeletonList } from '../components/LoadingSpinner';

export default function NewExpensePage() {
  const { id, expenseId } = useParams();
  const isEdit = Boolean(expenseId);
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
    const requests = [api.get(`/groups/${id}`)];
    if (isEdit) requests.push(api.get(`/groups/${id}/expenses/`));
    Promise.all(requests)
      .then(([groupRes, expensesRes]) => {
        setMembers(groupRes.data.members);
        const expense = expensesRes?.data.find((e) => e.id === expenseId);
        if (isEdit && !expense) {
          setError('Expense not found');
          return;
        }
        if (expense) {
          setTitle(expense.title);
          setAmount(expense.amount.toFixed(2));
          setPaidBy(expense.paid_by);
          setSplitType(expense.split_type);
          setCustomSplits(
            Object.fromEntries(
              expense.splits.map((s) => [s.user_id, s.amount.toFixed(2)])
            )
          );
        } else {
          setPaidBy(user?.id || groupRes.data.members[0]?.id || '');
        }
      })
      .catch((err) =>
        setError(err.response?.data?.detail || 'Failed to load group')
      )
      .finally(() => setLoading(false));
  }, [id, expenseId, isEdit, user]);

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
      if (isEdit) {
        await api.put(`/groups/${id}/expenses/${expenseId}`, body);
      } else {
        await api.post(`/groups/${id}/expenses/`, body);
      }
      navigate(`/groups/${id}`);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          (isEdit ? 'Failed to save expense' : 'Failed to add expense')
      );
      setSubmitting(false);
    }
  };

  if (loading) return <SkeletonList count={3} />;

  return (
    <div className="space-y-4">
      <h1 className="text-[28px] font-semibold text-ink">
        {isEdit ? 'Edit Expense' : 'Add Expense'}
      </h1>
      <form onSubmit={handleSubmit} className="card space-y-4 p-6">
        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-muted">
            Title
          </label>
          <input
            type="text"
            placeholder="e.g. Dinner at Luigi's"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={100}
            className="input"
          />
        </div>

        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-muted">
            Amount
          </label>
          <div className="relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-muted">
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
              className="input pl-8"
            />
          </div>
        </div>

        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-muted">
            Paid by
          </label>
          <select
            value={paidBy}
            onChange={(e) => setPaidBy(e.target.value)}
            className="input"
          >
            {members.map((m) => (
              <option key={m.id} value={m.id}>
                {m.id === user?.id
                  ? `${m.username || 'Member'} (you)`
                  : m.username || 'Member'}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-muted">
            Split type
          </label>
          <div className="grid grid-cols-2 gap-2">
            {['EQUAL', 'CUSTOM'].map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => setSplitType(type)}
                className={`min-h-[44px] rounded-[14px] border px-4 py-2.5 text-sm font-semibold transition-all duration-200  ${
                  splitType === type
                    ? 'border-rule-strong bg-sunk text-ink '
                    : 'border-rule bg-surface text-muted hover:bg-sunk'
                }`}
              >
                {type === 'EQUAL' ? 'Equal' : 'Custom'}
              </button>
            ))}
          </div>
        </div>

        {splitType === 'CUSTOM' && (
          <div className="space-y-2 rounded-[14px] border border-rule bg-surface p-4">
            {members.map((m) => (
              <div key={m.id} className="flex items-center gap-3">
                <span className="flex-1 truncate text-[15px] text-ink-soft">
                  {m.id === user?.id ? 'You' : m.username || 'Member'}
                </span>
                <div className="relative w-28">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted">
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
                    className="input py-2 pl-7 pr-2 text-sm"
                  />
                </div>
              </div>
            ))}
            <div
              className={`pt-2 text-right text-sm font-semibold tabular-nums ${
                customValid ? 'text-ink' : 'text-ink'
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
            variant="accent"
            disabled={submitting || (splitType === 'CUSTOM' && !customValid)}
            className="flex-1"
          >
            {submitting ? 'Saving…' : isEdit ? 'Save Changes' : 'Add Expense'}
          </Button>
        </div>
      </form>
    </div>
  );
}
