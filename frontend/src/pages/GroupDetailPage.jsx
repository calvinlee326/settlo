import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import api from '../api/axios';
import useAuthStore from '../store/authStore';
import Avatar from '../components/Avatar';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import ExpenseItem from '../components/ExpenseItem';
import LoadingSpinner from '../components/LoadingSpinner';

export default function GroupDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const [group, setGroup] = useState(null);
  const [expenses, setExpenses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [inviteCopied, setInviteCopied] = useState(false);

  const load = useCallback(async () => {
    try {
      const [groupRes, expensesRes] = await Promise.all([
        api.get(`/groups/${id}`),
        api.get(`/groups/${id}/expenses/`),
      ]);
      setGroup(groupRes.data);
      setExpenses(expensesRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load group');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const handleInvite = async () => {
    try {
      const { data } = await api.get(`/groups/${id}/invite`);
      await navigator.clipboard.writeText(data.invite_link);
      setInviteCopied(true);
      setTimeout(() => setInviteCopied(false), 2000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to get invite link');
    }
  };

  const handleDeleteExpense = async (expenseId) => {
    if (!window.confirm('Delete this expense?')) return;
    try {
      await api.delete(`/groups/${id}/expenses/${expenseId}`);
      setExpenses((prev) => prev.filter((e) => e.id !== expenseId));
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete expense');
    }
  };

  const handleDeleteGroup = async () => {
    if (!window.confirm('Delete this group and all its expenses?')) return;
    try {
      await api.delete(`/groups/${id}`);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete group');
    }
  };

  if (loading) return <LoadingSpinner />;
  if (!group) return <ErrorMessage message={error || 'Group not found'} />;

  const isCreator = user?.id === group.created_by;
  const total = expenses.reduce((sum, e) => sum + e.amount, 0);

  return (
    <div className="space-y-5">
      <div className="rounded-2xl bg-white p-5 shadow-sm">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900">{group.name}</h1>
            {group.description && (
              <p className="mt-1 text-sm text-slate-500">{group.description}</p>
            )}
          </div>
          {isCreator && (
            <button
              onClick={handleDeleteGroup}
              className="text-xs font-medium text-red-500 hover:underline"
            >
              Delete
            </button>
          )}
        </div>
        <div className="mt-4 flex items-center gap-2 overflow-x-auto pb-1">
          {group.members.map((member) => (
            <div key={member.id} className="flex flex-col items-center gap-1">
              <Avatar name={member.username || member.phone_number} size="sm" />
              <span className="max-w-[3.5rem] truncate text-[10px] text-slate-500">
                {member.id === user?.id
                  ? 'You'
                  : member.username || member.phone_number}
              </span>
            </div>
          ))}
          <button
            onClick={handleInvite}
            className="flex h-8 w-8 shrink-0 items-center justify-center self-start rounded-full border-2 border-dashed border-slate-300 text-slate-400 hover:border-primary-500 hover:text-primary-600"
            aria-label="Copy invite link"
          >
            +
          </button>
          {inviteCopied && (
            <span className="text-xs font-medium text-emerald-600">
              Invite link copied!
            </span>
          )}
        </div>
      </div>

      <ErrorMessage message={error} />

      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-900">Expenses</h2>
        <span className="text-sm font-medium text-slate-500">
          Total ${total.toFixed(2)}
        </span>
      </div>

      {expenses.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
          <p className="text-sm text-slate-500">
            No expenses yet. Tap + to add the first one.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {expenses.map((expense) => (
            <ExpenseItem
              key={expense.id}
              expense={expense}
              canDelete={
                expense.created_by === user?.id || isCreator
              }
              onDelete={() => handleDeleteExpense(expense.id)}
            />
          ))}
        </div>
      )}

      <Link to={`/groups/${id}/settle`}>
        <Button variant="secondary" className="mt-2 w-full py-3">
          Settle Up
        </Button>
      </Link>

      <Link
        to={`/groups/${id}/expenses/new`}
        aria-label="Add expense"
        className="fixed bottom-6 right-6 flex h-14 w-14 items-center justify-center rounded-full bg-primary-600 text-3xl font-light text-white shadow-lg transition hover:bg-primary-700"
      >
        +
      </Link>
    </div>
  );
}
