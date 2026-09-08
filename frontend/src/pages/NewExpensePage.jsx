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
  const [participants, setParticipants] = useState([]);
  const [history, setHistory] = useState([]);
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
          setParticipants(expense.splits.map((s) => s.user_id));
          setCustomSplits(
            Object.fromEntries(
              expense.splits.map((s) => [s.user_id, s.amount.toFixed(2)])
            )
          );
        } else {
          setPaidBy(user?.id || groupRes.data.members[0]?.id || '');
          setParticipants(groupRes.data.members.map((m) => m.id));
        }
      })
      .catch((err) =>
        setError(err.response?.data?.detail || 'Failed to load group')
      )
      .finally(() => setLoading(false));
  }, [id, expenseId, isEdit, user]);

  useEffect(() => {
    if (!isEdit) return;
    api
      .get(`/groups/${id}/expenses/${expenseId}/history`)
      .then(({ data }) => setHistory(data))
      .catch(() => {});
  }, [id, expenseId, isEdit]);

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

  // Mirrors the backend's equal_split: floor to the cent, then hand the
  // leftover cents to the first participants in member order.
  const equalShares = useMemo(() => {
    const chosen = members.filter((m) => participants.includes(m.id));
    if (chosen.length === 0 || !(totalAmount > 0)) return {};
    const cents = Math.round(totalAmount * 100);
    const base = Math.floor(cents / chosen.length);
    const extra = cents - base * chosen.length;
    return Object.fromEntries(
      chosen.map((m, i) => [m.id, (base + (i < extra ? 1 : 0)) / 100])
    );
  }, [members, participants, totalAmount]);

  const toggleParticipant = (memberId) =>
    setParticipants((prev) =>
      prev.includes(memberId)
        ? prev.filter((existing) => existing !== memberId)
        : [...prev, memberId]
    );

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
    if (splitType === 'EQUAL' && participants.length === 0) {
      setError('Pick at least one person to split between');
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
      } else {
        body.participants = participants;
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
          <label htmlFor="expense-title" className="mb-1.5 block text-[13px] font-medium text-muted">
            Title
          </label>
          <input
            id="expense-title"
            type="text"
            placeholder="e.g. Dinner at Luigi's"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={100}
            className="input"
          />
        </div>

        <div>
          <label htmlFor="expense-amount" className="mb-1.5 block text-[13px] font-medium text-muted">
            Amount
          </label>
          <div className="relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-muted">
              $
            </span>
            <input
              id="expense-amount"
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
          <label htmlFor="expense-paid-by" className="mb-1.5 block text-[13px] font-medium text-muted">
            Paid by
          </label>
          <select
            id="expense-paid-by"
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

        <fieldset>
          <legend className="mb-1.5 block text-[13px] font-medium text-muted">
            Split type
          </legend>
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
        </fieldset>

        {splitType === 'EQUAL' && (
          <fieldset className="space-y-2 rounded-[14px] border border-rule bg-surface p-4">
            <legend className="px-1 text-[13px] font-medium text-muted">
              Split between
            </legend>
            {members.map((m) => {
              const checked = participants.includes(m.id);
              return (
                <label
                  key={m.id}
                  htmlFor={`participant-${m.id}`}
                  className="flex cursor-pointer items-center gap-3 py-1"
                >
                  <input
                    id={`participant-${m.id}`}
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleParticipant(m.id)}
                    className="h-4 w-4 shrink-0 accent-ink"
                  />
                  <span className="flex-1 truncate text-[15px] text-ink-soft">
                    {m.id === user?.id ? 'You' : m.username || 'Member'}
                  </span>
                  <span className="text-sm tabular-nums text-muted">
                    {checked && equalShares[m.id] !== undefined
                      ? `$${equalShares[m.id].toFixed(2)}`
                      : '—'}
                  </span>
                </label>
              );
            })}
            <p className="pt-2 text-right text-sm font-semibold tabular-nums text-ink">
              {participants.length === 0
                ? 'Pick at least one person'
                : totalAmount > 0
                  ? `$${totalAmount.toFixed(2)} split ${participants.length} way${participants.length === 1 ? '' : 's'}`
                  : `Split ${participants.length} way${participants.length === 1 ? '' : 's'}`}
            </p>
          </fieldset>
        )}

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

        {history.length > 0 && (
          <div className="space-y-1 rounded-[14px] border border-rule bg-surface p-4">
            <h2 className="text-[13px] font-medium uppercase tracking-wide text-muted">
              Edit history
            </h2>
            {history.map((revision) => (
              <p key={revision.id} className="text-[13px] text-muted">
                Was &ldquo;{revision.snapshot.title}&rdquo; for $
                {revision.snapshot.amount.toFixed(2)} &middot; changed by{' '}
                {revision.changed_by_username || 'someone'} on{' '}
                {new Date(revision.changed_at).toLocaleDateString()}
              </p>
            ))}
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
            disabled={
              submitting ||
              (splitType === 'CUSTOM' && !customValid) ||
              (splitType === 'EQUAL' && participants.length === 0)
            }
            className="flex-1"
          >
            {submitting ? 'Saving…' : isEdit ? 'Save Changes' : 'Add Expense'}
          </Button>
        </div>
      </form>
    </div>
  );
}
