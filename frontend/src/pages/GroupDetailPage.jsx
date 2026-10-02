import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import useSWR from 'swr';
import api from '../api/axios';
import useAuthStore from '../store/authStore';
import Avatar from '../components/Avatar';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import ExpenseItem from '../components/ExpenseItem';
import { SkeletonList } from '../components/LoadingSpinner';
import { isValidHandle, normalizeHandle } from '../lib/handle';

// Cap the entry stagger: past this index every card animates together, so a
// long list finishes in ~550ms instead of growing 50ms per row.
const STAGGER_CAP = 4;

export default function GroupDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const { data: group, error: groupError, mutate: mutateGroup } = useSWR(`/groups/${id}`);
  const {
    data: expensesData,
    error: expensesError,
    mutate: mutateExpenses,
  } = useSWR(`/groups/${id}/expenses/`);
  const { data: friends = [] } = useSWR('/friends');
  const [error, setError] = useState('');
  const [inviteLink, setInviteLink] = useState('');
  const [linkCopied, setLinkCopied] = useState(false);
  const [inviteContact, setInviteContact] = useState('');
  const [inviteFriendId, setInviteFriendId] = useState('');
  const [inviteNotice, setInviteNotice] = useState('');
  // ponytail: one busy flag for the whole page. Split per-action if two
  // of these ever need to run at once.
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  // Warm the settle screen's data on hover/touch so it opens from cache.
  const [warmSettle, setWarmSettle] = useState(false);
  useSWR(warmSettle ? `/groups/${id}/settlements/` : null);
  const expenses = expensesData ?? [];

  const sendInvite = async () => {
    setError('');
    setInviteNotice('');
    const handle = normalizeHandle(inviteContact);
    if (!isValidHandle(handle)) {
      setError("Enter the person's ID");
      return;
    }
    setBusy(true);
    try {
      await api.post('/group-invitations', { group_id: id, handle });
      setInviteContact('');
      setInviteNotice('Invite sent');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to send invite');
    } finally {
      setBusy(false);
    }
  };

  const addFriend = async (friendId) => {
    setError('');
    setBusy(true);
    try {
      const { data } = await api.post(`/groups/${id}/members`, { user_id: friendId });
      mutateGroup(data, { revalidate: false });
      setInviteFriendId('');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add friend');
    } finally {
      setBusy(false);
    }
  };

  const removeMember = async (memberId, name) => {
    if (!window.confirm(`Remove ${name} from this group?`)) return;
    setError('');
    setBusy(true);
    try {
      await api.delete(`/groups/${id}/members/${memberId}`);
      mutateGroup({
          ...group,
          members: group.members.filter((m) => m.id !== memberId),
          member_count: group.member_count - 1,
        });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remove member');
    } finally {
      setBusy(false);
    }
  };

  const handleInvite = async () => {
    setError('');
    setBusy(true);
    try {
      const { data } = await api.get(`/groups/${id}/invite`);
      setInviteLink(`${window.location.origin}/invite/${data.invite_token}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to get invite link');
    } finally {
      setBusy(false);
    }
  };

  const copyInviteLink = async () => {
    try {
      await navigator.clipboard.writeText(inviteLink);
      setLinkCopied(true);
    } catch {
      setError('Could not copy. Select the link and copy it manually.');
    }
  };

  const handleDeleteExpense = async (expenseId) => {
    if (!window.confirm('Delete this expense?')) return;
    setError('');
    setBusy(true);
    try {
      await api.delete(`/groups/${id}/expenses/${expenseId}`);
      mutateExpenses(expenses.filter((e) => e.id !== expenseId));
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete expense');
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteGroup = async () => {
    if (!window.confirm('Delete this group and all its expenses?')) return;
    setError('');
    setBusy(true);
    try {
      await api.delete(`/groups/${id}`);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete group');
      setBusy(false);
    }
  };

  const leaveGroup = async () => {
    if (!window.confirm('Leave this group?')) return;
    setError('');
    setBusy(true);
    try {
      await api.delete(`/groups/${id}/members/${user.id}`);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to leave group');
      setBusy(false);
    }
  };

  const visibleExpenses = useMemo(() => {
    const needle = search.trim().toLowerCase();
    // toDate is an inclusive day, so compare against the end of it.
    const from = fromDate ? new Date(`${fromDate}T00:00:00`) : null;
    const to = toDate ? new Date(`${toDate}T23:59:59.999`) : null;
    return expenses.filter((e) => {
      if (
        needle &&
        !e.title.toLowerCase().includes(needle) &&
        !(e.paid_by_username || '').toLowerCase().includes(needle)
      ) {
        return false;
      }
      const at = new Date(e.created_at);
      if (from && at < from) return false;
      if (to && at > to) return false;
      return true;
    });
  }, [expenses, search, fromDate, toDate]);

  const filtersActive = Boolean(search.trim() || fromDate || toDate);

  const loadError = groupError || expensesError;
  if (!loadError && (!group || !expensesData)) return <SkeletonList count={4} />;
  if (loadError && !(group && expensesData)) {
    return (
      <ErrorMessage
        message={loadError.response?.data?.detail || 'Failed to load group'}
      />
    );
  }

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
              disabled={busy}
              className="text-[13px] font-medium text-muted transition-colors hover:text-ink disabled:opacity-40"
            >
              Delete
            </button>
          ) : !isSettled ? (
            <button
              onClick={leaveGroup}
              disabled={busy}
              className="text-[13px] font-medium text-muted transition-colors hover:text-ink disabled:opacity-40"
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
                    disabled={busy}
                    aria-label={`Remove ${member.username || 'member'}`}
                    className="absolute -right-1 -top-1 z-10 flex h-4 w-4 items-center justify-center rounded-full bg-ink text-[11px] font-bold leading-none text-white ring-2 ring-white disabled:opacity-40"
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
            disabled={busy}
            className="flex h-8 w-8 shrink-0 items-center justify-center self-start rounded-full border-2 border-dashed border-rule-strong text-muted transition-colors hover:border-rule-strong hover:text-ink disabled:opacity-40"
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
          <div className="card space-y-2 p-4">
            <label htmlFor="expense-search" className="sr-only">
              Search expenses
            </label>
            <input
              id="expense-search"
              type="search"
              placeholder="Search by title or who paid"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl bg-sunk px-3 py-2 text-[13px] text-ink placeholder-muted outline-none"
            />
            <div className="flex flex-wrap items-center gap-2">
              <label htmlFor="expense-from" className="text-[13px] text-muted">
                From
              </label>
              <input
                id="expense-from"
                type="date"
                value={fromDate}
                max={toDate || undefined}
                onChange={(e) => setFromDate(e.target.value)}
                className="min-w-0 flex-1 rounded-xl bg-sunk px-3 py-2 text-[13px] text-ink outline-none"
              />
              <label htmlFor="expense-to" className="text-[13px] text-muted">
                To
              </label>
              <input
                id="expense-to"
                type="date"
                value={toDate}
                min={fromDate || undefined}
                onChange={(e) => setToDate(e.target.value)}
                className="min-w-0 flex-1 rounded-xl bg-sunk px-3 py-2 text-[13px] text-ink outline-none"
              />
              {filtersActive && (
                <button
                  type="button"
                  onClick={() => {
                    setSearch('');
                    setFromDate('');
                    setToDate('');
                  }}
                  className="shrink-0 text-[13px] font-medium text-muted underline hover:text-ink"
                >
                  Clear
                </button>
              )}
            </div>
            {filtersActive && (
              <p className="text-[13px] text-muted" role="status">
                Showing {visibleExpenses.length} of {expenses.length} expenses
              </p>
            )}
          </div>
          {visibleExpenses.length === 0 ? (
            <p className="rounded-card border border-dashed border-rule bg-surface p-6 text-center text-[15px] text-muted">
              No expenses match those filters.
            </p>
          ) : null}
          {visibleExpenses.map((expense, i) => (
            <ExpenseItem
              key={expense.id}
              expense={expense}
              style={{ animationDelay: `${Math.min(i, STAGGER_CAP) * 50}ms` }}
              canDelete={!isSettled && (expense.created_by === user?.id || isCreator)}
              editTo={
                !isSettled && (expense.created_by === user?.id || isCreator)
                  ? `/groups/${id}/expenses/${expense.id}/edit`
                  : undefined
              }
              onDelete={() => handleDeleteExpense(expense.id)}
            />
          ))}
        </div>
      )}

      {!isSettled && expenses.length > 0 && (
        <Link
          to={`/groups/${id}/settle`}
          onPointerEnter={() => setWarmSettle(true)}
          onPointerLeave={() => setWarmSettle(false)}
          className="block"
        >
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
            <div className="space-y-2">
              <label htmlFor="invite-link" className="block text-[13px] font-medium text-muted">Share invite link</label>
              <div className="flex gap-2">
                <input
                  id="invite-link"
                  readOnly
                  value={inviteLink}
                  onFocus={(e) => e.target.select()}
                  className="min-w-0 flex-1 rounded-xl bg-sunk px-3 py-2 text-[13px] text-ink outline-none"
                />
                <button
                  onClick={copyInviteLink}
                  className="shrink-0 rounded-xl bg-ink px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-80"
                >
                  {linkCopied ? 'Copied' : 'Copy'}
                </button>
              </div>
            </div>
            <div className="space-y-2 border-t border-rule pt-3">
              <label htmlFor="invite-contact" className="block text-[13px] font-medium text-muted">Invite by ID</label>
              <div className="flex gap-2">
                <input
                  id="invite-contact"
                  type="text"
                  autoCapitalize="none"
                  autoCorrect="off"
                  placeholder="Their ID"
                  value={inviteContact}
                  onChange={(e) => setInviteContact(e.target.value)}
                  className="min-w-0 flex-1 rounded-xl bg-sunk px-3 py-2 text-[13px] text-ink placeholder-muted outline-none"
                />
                <button
                  onClick={sendInvite}
                  disabled={busy || !inviteContact.trim()}
                  className="shrink-0 rounded-xl bg-ink px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-80 disabled:opacity-40"
                >
                  {busy ? 'Sending…' : 'Invite'}
                </button>
              </div>
              {inviteNotice && <p className="text-[12px] text-ink">{inviteNotice}</p>}
              <ErrorMessage message={error} />
            </div>
            {(() => {
              if (friends.length === 0) return null;
              const memberIds = new Set(group.members.map((m) => m.id));
              const addable = friends.filter((f) => !memberIds.has(f.id));
              return (
                <div className="space-y-2 border-t border-rule pt-3">
                  <label htmlFor="invite-friend" className="block text-[13px] font-medium text-muted">Add a friend</label>
                  {addable.length === 0 ? (
                    <p className="text-[13px] text-muted">
                      All your friends are already in this group.
                    </p>
                  ) : (
                    <div className="flex gap-2">
                      <select
                        id="invite-friend"
                        value={inviteFriendId}
                        onChange={(e) => setInviteFriendId(e.target.value)}
                        className="min-w-0 flex-1 rounded-xl bg-sunk px-3 py-2 text-[13px] text-ink outline-none"
                      >
                        <option value="">Select a friend</option>
                        {addable.map((f) => (
                          <option key={f.id} value={f.id} className="bg-zinc-900">
                            {f.username || f.handle}
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={() => addFriend(inviteFriendId)}
                        disabled={busy || !inviteFriendId}
                        className="shrink-0 rounded-xl bg-ink px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-80 disabled:opacity-40"
                      >
                        {busy ? 'Adding…' : 'Add'}
                      </button>
                    </div>
                  )}
                </div>
              );
            })()}
            <button
              onClick={() => { setInviteLink(''); setInviteNotice(''); setLinkCopied(false); }}
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
