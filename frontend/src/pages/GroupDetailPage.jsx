import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import api from '../api/axios';
import useAuthStore from '../store/authStore';
import Avatar from '../components/Avatar';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import ExpenseItem from '../components/ExpenseItem';
import { SkeletonList } from '../components/LoadingSpinner';

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

  if (loading) return <SkeletonList count={4} />;
  if (!group) return <ErrorMessage message={error || 'Group not found'} />;

  const isCreator = user?.id === group.created_by;
  const total = expenses.reduce((sum, e) => sum + e.amount, 0);

  return (
    <div className="space-y-5">
      <div className="glass p-5">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-[28px] font-semibold text-white">
              {group.name}
            </h1>
            {group.description && (
              <p className="mt-1 text-[15px] text-white/55">
                {group.description}
              </p>
            )}
          </div>
          {isCreator && (
            <button
              onClick={handleDeleteGroup}
              className="text-[13px] font-medium text-red-400/80 transition-colors hover:text-red-400"
            >
              Delete
            </button>
          )}
        </div>
        <div className="mt-4 flex items-center gap-2 overflow-x-auto pb-1">
          {group.members.map((member) => (
            <div key={member.id} className="flex flex-col items-center gap-1">
              <Avatar name={member.username || member.phone_number} size="sm" />
              <span className="max-w-[3.5rem] truncate text-[10px] text-white/50">
                {member.id === user?.id
                  ? 'You'
                  : member.username || member.phone_number}
              </span>
            </div>
          ))}
          <button
            onClick={handleInvite}
            className="flex h-8 w-8 shrink-0 items-center justify-center self-start rounded-full border-2 border-dashed border-white/25 text-white/40 transition-colors hover:border-violet-400/70 hover:text-violet-300"
            aria-label="Copy invite link"
          >
            +
          </button>
          {inviteCopied && (
            <span className="text-xs font-medium text-emerald-400">
              Invite link copied!
            </span>
          )}
        </div>
      </div>

      <ErrorMessage message={error} />

      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium text-white/90">Expenses</h2>
        <span className="text-sm font-medium tabular-nums text-white/55">
          Total ${total.toFixed(2)}
        </span>
      </div>

      {expenses.length === 0 ? (
        <div className="rounded-glass border border-dashed border-white/15 bg-white/[0.03] p-8 text-center">
          <p className="text-[15px] text-white/55">
            No expenses yet. Tap + to add the first one.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {expenses.map((expense, i) => (
            <ExpenseItem
              key={expense.id}
              expense={expense}
              style={{ animationDelay: `${i * 50}ms` }}
              canDelete={expense.created_by === user?.id || isCreator}
              onDelete={() => handleDeleteExpense(expense.id)}
            />
          ))}
        </div>
      )}

      <Link to={`/groups/${id}/settle`} className="block">
        <Button variant="primary" className="mt-2 w-full">
          Settle Up
        </Button>
      </Link>

      <Link
        to={`/groups/${id}/expenses/new`}
        aria-label="Add expense"
        className="fab"
      >
        +
      </Link>
    </div>
  );
}
