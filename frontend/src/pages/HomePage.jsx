import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/axios';
import ErrorMessage from '../components/ErrorMessage';
import GroupCard from '../components/GroupCard';
import { SkeletonList } from '../components/LoadingSpinner';

// Cap the entry stagger: past this index every card animates together, so a
// long list finishes in ~550ms instead of growing 50ms per row.
const STAGGER_CAP = 4;

export default function HomePage() {
  const [groups, setGroups] = useState([]);
  const [friends, setFriends] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [invites, setInvites] = useState([]);
  const [expenseGroupId, setExpenseGroupId] = useState('');

  const loadInvites = () =>
    api
      .get('/group-invitations')
      .then(({ data }) => setInvites(data))
      .catch(() => {});

  useEffect(() => {
    loadInvites();
  }, []);

  const respondInvite = async (inviteId, action) => {
    try {
      await api.post(`/group-invitations/${inviteId}/${action}`);
      await loadInvites();
      if (action === 'accept') {
        const { data } = await api.get('/groups/');
        setGroups(data);
      }
    } catch {
      // ignore; list reload covers state
    }
  };

  useEffect(() => {
    Promise.all([api.get('/groups/'), api.get('/friends')])
      .then(([groupsRes, friendsRes]) => {
        setGroups(groupsRes.data);
        setFriends(friendsRes.data);
      })
      .catch((err) =>
        setError(err.response?.data?.detail || 'Failed to load groups')
      )
      .finally(() => setLoading(false));
  }, []);

  const activeGroups = useMemo(
    () => groups.filter((g) => !g.settled_at),
    [groups]
  );

  // Group balances and friend balances never overlap: friend net_balance counts
  // only direct expenses (group_id is null), so summing both double-counts nothing.
  const outstanding = useMemo(() => {
    const fromGroups = activeGroups
      .filter((g) => Math.abs(g.my_balance || 0) >= 0.005)
      .map((g) => ({
        key: `group-${g.id}`,
        name: g.name,
        balance: g.my_balance,
        to: `/groups/${g.id}/settle`,
      }));
    const fromFriends = friends
      .filter((f) => Math.abs(f.net_balance || 0) >= 0.005)
      .map((f) => ({
        key: `friend-${f.id}`,
        name: f.username || f.phone_number,
        balance: f.net_balance,
        to: '/friends',
      }));
    return [...fromGroups, ...fromFriends].sort(
      (a, b) => Math.abs(b.balance) - Math.abs(a.balance)
    );
  }, [activeGroups, friends]);

  const owed = outstanding
    .filter((o) => o.balance > 0)
    .reduce((sum, o) => sum + o.balance, 0);
  const owe = outstanding
    .filter((o) => o.balance < 0)
    .reduce((sum, o) => sum - o.balance, 0);

  useEffect(() => {
    if (!expenseGroupId && activeGroups.length > 0) {
      setExpenseGroupId(activeGroups[0].id);
    }
  }, [activeGroups, expenseGroupId]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[28px] font-semibold text-ink">Home</h1>
        {!loading && (
          <div className="mt-3 grid grid-cols-2 gap-3">
            <div className="card p-4">
              <p className="text-[13px] font-medium uppercase tracking-wide text-muted">
                You owe
              </p>
              <p className="mt-1 text-[22px] font-semibold tabular-nums text-ink">
                ${owe.toFixed(2)}
              </p>
            </div>
            <div className="card p-4">
              <p className="text-[13px] font-medium uppercase tracking-wide text-muted">
                You&rsquo;re owed
              </p>
              <p className="mt-1 text-[22px] font-semibold tabular-nums text-ink">
                ${owed.toFixed(2)}
              </p>
            </div>
          </div>
        )}
      </div>

      {!loading && (activeGroups.length > 0 || friends.length > 0) && (
        <div className="card flex flex-wrap items-center gap-2 p-4">
          {activeGroups.length > 0 && (
            <>
              <label htmlFor="expense-group" className="sr-only">
                Group to add an expense to
              </label>
              <select
                id="expense-group"
                value={expenseGroupId}
                onChange={(e) => setExpenseGroupId(e.target.value)}
                className="min-w-0 flex-1 rounded-xl bg-sunk px-3 py-2 text-[13px] text-ink outline-none"
              >
                {activeGroups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
              <Link
                to={`/groups/${expenseGroupId || activeGroups[0].id}/expenses/new`}
                className="shrink-0 rounded-xl bg-ink px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-80"
              >
                Add expense
              </Link>
            </>
          )}
          <Link
            to="/friends/expenses/new"
            className="shrink-0 rounded-xl bg-sunk px-4 py-2 text-[13px] font-medium text-ink-soft transition-opacity hover:opacity-80"
          >
            With a friend
          </Link>
        </div>
      )}

      {outstanding.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-lg font-medium text-ink">Outstanding</h2>
          {outstanding.map((item) => (
            <Link
              key={item.key}
              to={item.to}
              className="card flex items-center justify-between gap-3 p-4 transition-colors hover:border-rule-strong"
            >
              <span className="min-w-0 flex-1 truncate text-[15px] text-ink">
                {item.name}
              </span>
              <span className="shrink-0 text-[13px] font-semibold tabular-nums text-ink">
                {item.balance > 0
                  ? `You're owed $${item.balance.toFixed(2)}`
                  : `You owe $${Math.abs(item.balance).toFixed(2)}`}
              </span>
            </Link>
          ))}
        </div>
      )}
      <ErrorMessage message={error} />
      {invites.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-lg font-medium text-ink">Group invitations</h2>
          {invites.map((inv) => (
            <div key={inv.id} className="card flex items-center justify-between p-4">
              <div>
                <p className="text-[15px] font-medium text-ink">{inv.group_name}</p>
                <p className="text-[13px] text-muted">
                  from {inv.invited_by_username || 'someone'}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => respondInvite(inv.id, 'accept')}
                  className="rounded-xl bg-ink px-3 py-1.5 text-[13px] font-medium text-white hover:opacity-80"
                >
                  Join
                </button>
                <button
                  onClick={() => respondInvite(inv.id, 'decline')}
                  className="rounded-xl bg-sunk px-3 py-1.5 text-[13px] font-medium text-ink-soft hover:opacity-80"
                >
                  Decline
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      {loading ? (
        <SkeletonList count={3} />
      ) : activeGroups.length === 0 && !error ? (
        <div className="space-y-4 rounded-card border border-dashed border-rule bg-surface p-6 text-center">
          <div>
            <p className="text-[17px] font-semibold text-ink">Welcome to Settlo</p>
            <p className="mt-1 text-[14px] text-muted">
              Split bills with friends and settle up with the fewest payments.
            </p>
          </div>
          <ol className="mx-auto max-w-xs space-y-2 text-left text-[14px] text-ink-soft">
            <li>
              <span className="font-semibold text-ink">1.</span> Create a group and invite people by phone or QR code.
            </li>
            <li>
              <span className="font-semibold text-ink">2.</span> Add expenses — split equally or with custom amounts.
            </li>
            <li>
              <span className="font-semibold text-ink">3.</span> Settle up to see who pays whom.
            </li>
          </ol>
          <Link
            to="/groups/new"
            className="inline-block rounded-xl bg-ink px-5 py-2.5 text-[14px] font-medium text-white transition-opacity hover:opacity-80"
          >
            Create your first group
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          <h2 className="text-lg font-medium text-ink">My groups</h2>
          {activeGroups.map((group, i) => (
            <GroupCard
              key={group.id}
              group={group}
              style={{ animationDelay: `${Math.min(i, STAGGER_CAP) * 50}ms` }}
            />
          ))}
        </div>
      )}
      <Link to="/groups/new" aria-label="Create new group" className="fab">
        +
      </Link>
    </div>
  );
}
