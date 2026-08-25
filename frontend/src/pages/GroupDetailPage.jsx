import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { QRCodeSVG } from 'qrcode.react';
import api from '../api/axios';
import useAuthStore from '../store/authStore';
import Avatar from '../components/Avatar';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import ExpenseItem from '../components/ExpenseItem';
import { SkeletonList } from '../components/LoadingSpinner';
import { formatPhone } from '../lib/phone';

export default function GroupDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const [group, setGroup] = useState(null);
  const [expenses, setExpenses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [inviteLink, setInviteLink] = useState('');
  const [friends, setFriends] = useState([]);
  const [invitePhone, setInvitePhone] = useState('');
  const [inviteFriendId, setInviteFriendId] = useState('');
  const [inviteNotice, setInviteNotice] = useState('');

  useEffect(() => {
    api
      .get('/friends')
      .then(({ data }) => setFriends(data))
      .catch(() => {});
  }, []);

  const sendPhoneInvite = async () => {
    setError('');
    setInviteNotice('');
    let digits = invitePhone.replace(/\D/g, '');
    if (digits.length === 11 && digits.startsWith('1')) digits = digits.slice(1);
    if (digits.length !== 10) {
      setError('Enter a valid 10-digit US phone number');
      return;
    }
    try {
      await api.post('/group-invitations', {
        group_id: id,
        phone_number: `+1${digits}`,
      });
      setInvitePhone('');
      setInviteNotice('Invite sent');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to send invite');
    }
  };

  const addFriend = async (friendId) => {
    setError('');
    try {
      const { data } = await api.post(`/groups/${id}/members`, { user_id: friendId });
      setGroup(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add friend');
    }
  };

  const removeMember = async (memberId, name) => {
    if (!window.confirm(`Remove ${name} from this group?`)) return;
    setError('');
    try {
      await api.delete(`/groups/${id}/members/${memberId}`);
      setGroup((g) => ({
        ...g,
        members: g.members.filter((m) => m.id !== memberId),
        member_count: g.member_count - 1,
      }));
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remove member');
    }
  };

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
      setInviteLink(`${window.location.origin}/invite/${data.invite_token}`);
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

  const leaveGroup = async () => {
    if (!window.confirm('Leave this group?')) return;
    try {
      await api.delete(`/groups/${id}/members/${user.id}`);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to leave group');
    }
  };

  if (loading) return <SkeletonList count={4} />;
  if (!group) return <ErrorMessage message={error || 'Group not found'} />;

  const isCreator = user?.id === group.created_by;
  const isSettled = Boolean(group.settled_at);
  const total = expenses.reduce((sum, e) => sum + e.amount, 0);

  return (
    <div className="space-y-5">
      <div className="card p-5">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-[28px] font-semibold text-ink">
              {group.name}
            </h1>
            {group.description && (
              <p className="mt-1 text-[15px] text-muted">
                {group.description}
              </p>
            )}
          </div>
          {isCreator ? (
            <button
              onClick={handleDeleteGroup}
              className="text-[13px] font-medium text-muted transition-colors hover:text-ink"
            >
              Delete
            </button>
          ) : !isSettled ? (
            <button
              onClick={leaveGroup}
              className="text-[13px] font-medium text-muted transition-colors hover:text-ink"
            >
              Leave
            </button>
          ) : null}
        </div>
        <div className="mt-4 flex items-center gap-2 overflow-x-auto pb-1 pt-1">
          {group.members.map((member) => (
            <div key={member.id} className="flex shrink-0 flex-col items-center gap-1">
              <div className="relative">
                {isCreator && !isSettled && member.id !== group.created_by && (
                  <button
                    onClick={() => removeMember(member.id, member.username || 'this member')}
                    aria-label={`Remove ${member.username || 'member'}`}
                    className="absolute -right-1 -top-1 z-10 flex h-4 w-4 items-center justify-center rounded-full bg-ink text-[11px] font-bold leading-none text-white ring-2 ring-white"
                  >
                    ×
                  </button>
                )}
                <Avatar name={member.username || 'Member'} size="sm" />
              </div>
              <span className="max-w-[3.5rem] truncate text-[10px] text-muted">
                {member.id === user?.id ? 'You' : member.username || 'Member'}
              </span>
            </div>
          ))}
          <button
            onClick={handleInvite}
            className="flex h-8 w-8 shrink-0 items-center justify-center self-start rounded-full border-2 border-dashed border-rule-strong text-muted transition-colors hover:border-rule-strong hover:text-ink"
            aria-label="Show invite link"
          >
            +
          </button>
        </div>
      </div>

      <ErrorMessage message={error} />

      {isSettled && (
        <div className="rounded-card border border-rule bg-sunk p-3 text-center text-[14px] text-ink">
          Settled — this group is archived in Payment History.
        </div>
      )}

      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium text-ink">Expenses</h2>
        <span className="text-sm font-medium tabular-nums text-muted">
          Total ${total.toFixed(2)}
        </span>
      </div>

      {expenses.length === 0 ? (
        <div className="rounded-card border border-dashed border-rule bg-surface p-8 text-center">
          <p className="text-[15px] text-muted">
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
              canDelete={!isSettled && (expense.created_by === user?.id || isCreator)}
              onDelete={() => handleDeleteExpense(expense.id)}
            />
          ))}
        </div>
      )}

      {!isSettled && expenses.length > 0 && (
        <Link to={`/groups/${id}/settle`} className="block">
          <Button variant="primary" className="mt-2 w-full">
            Settle Up
          </Button>
        </Link>
      )}

      {!isSettled && (
        <Link
          to={`/groups/${id}/expenses/new`}
          aria-label="Add expense"
          className="fab"
        >
          +
        </Link>
      )}

      {inviteLink && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
          <div className="card w-full max-w-sm space-y-4 p-6">
            <h2 className="text-[17px] font-semibold text-ink">Invite to group</h2>
            <div className="flex flex-col items-center gap-3">
              <div className="rounded-2xl bg-white p-3">
                <QRCodeSVG value={inviteLink} size={160} />
              </div>
              <p className="text-[13px] text-muted">Scan to join</p>
            </div>
            <div className="space-y-2 border-t border-rule pt-3">
              <p className="text-[13px] font-medium text-muted">Invite by phone</p>
              <div className="flex gap-2">
                <input
                  type="tel"
                  inputMode="numeric"
                  placeholder="909-555-0101"
                  value={invitePhone}
                  onChange={(e) => setInvitePhone(formatPhone(e.target.value))}
                  className="min-w-0 flex-1 rounded-xl bg-sunk px-3 py-2 text-[13px] text-ink placeholder-muted outline-none"
                />
                <button
                  onClick={sendPhoneInvite}
                  disabled={!invitePhone.trim()}
                  className="shrink-0 rounded-xl bg-ink px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-80 disabled:opacity-40"
                >
                  Invite
                </button>
              </div>
              {inviteNotice && <p className="text-[12px] text-ink">{inviteNotice}</p>}
            </div>
            {(() => {
              if (friends.length === 0) return null;
              const memberIds = new Set(group.members.map((m) => m.id));
              const addable = friends.filter((f) => !memberIds.has(f.id));
              return (
                <div className="space-y-2 border-t border-rule pt-3">
                  <p className="text-[13px] font-medium text-muted">Add a friend</p>
                  {addable.length === 0 ? (
                    <p className="text-[13px] text-muted">
                      All your friends are already in this group.
                    </p>
                  ) : (
                    <div className="flex gap-2">
                      <select
                        value={inviteFriendId}
                        onChange={(e) => setInviteFriendId(e.target.value)}
                        className="min-w-0 flex-1 rounded-xl bg-sunk px-3 py-2 text-[13px] text-ink outline-none"
                      >
                        <option value="">Select a friend</option>
                        {addable.map((f) => (
                          <option key={f.id} value={f.id} className="bg-zinc-900">
                            {f.username || f.phone_number}
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={() => { addFriend(inviteFriendId); setInviteFriendId(''); }}
                        disabled={!inviteFriendId}
                        className="shrink-0 rounded-xl bg-ink px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-80 disabled:opacity-40"
                      >
                        Add
                      </button>
                    </div>
                  )}
                </div>
              );
            })()}
            <button
              onClick={() => { setInviteLink(''); setInviteNotice(''); }}
              className="w-full rounded-xl bg-sunk py-2 text-[14px] font-medium text-ink-soft transition-opacity hover:opacity-80"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
