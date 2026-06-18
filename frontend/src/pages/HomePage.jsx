import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../api/axios';
import ErrorMessage from '../components/ErrorMessage';
import GroupCard from '../components/GroupCard';
import { SkeletonList } from '../components/LoadingSpinner';
import useAuthStore from '../store/authStore';
import PaymentHistoryItem from '../components/PaymentHistoryItem';

export default function HomePage() {
  const navigate = useNavigate();
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [joinInput, setJoinInput] = useState('');
  const [invites, setInvites] = useState([]);
  const user = useAuthStore((s) => s.user);

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

  const handleJoin = () => {
    const val = joinInput.trim();
    if (!val) return;
    let token = val;
    try {
      const url = new URL(val);
      const parts = url.pathname.split('/').filter(Boolean);
      token = parts[parts.length - 1];
    } catch {
      // bare token
    }
    navigate(`/invite/${token}`);
  };

  useEffect(() => {
    api
      .get('/groups/')
      .then(({ data }) => setGroups(data))
      .catch((err) =>
        setError(err.response?.data?.detail || 'Failed to load groups')
      )
      .finally(() => setLoading(false));
  }, []);

  const activeGroups = groups.filter((g) => !g.settled_at);
  const settledGroups = groups.filter((g) => g.settled_at);

  return (
    <div className="space-y-4">
      <h1 className="text-[28px] font-semibold text-white">My Groups</h1>
      <ErrorMessage message={error} />
      {invites.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-lg font-medium text-white/90">Group invitations</h2>
          {invites.map((inv) => (
            <div key={inv.id} className="glass flex items-center justify-between p-4">
              <div>
                <p className="text-[15px] font-medium text-white/85">{inv.group_name}</p>
                <p className="text-[13px] text-white/45">
                  from {inv.invited_by_username || 'someone'}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => respondInvite(inv.id, 'accept')}
                  className="rounded-xl bg-violet-500 px-3 py-1.5 text-[13px] font-medium text-white hover:opacity-80"
                >
                  Join
                </button>
                <button
                  onClick={() => respondInvite(inv.id, 'decline')}
                  className="rounded-xl bg-white/10 px-3 py-1.5 text-[13px] font-medium text-white/70 hover:opacity-80"
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
      ) : groups.length === 0 && !error ? (
        <div className="rounded-glass border border-dashed border-white/15 bg-white/[0.03] p-8 text-center">
          <p className="text-[15px] text-white/55">
            No groups yet. Create one to start splitting bills with friends.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {activeGroups.map((group, i) => (
            <GroupCard
              key={group.id}
              group={group}
              style={{ animationDelay: `${i * 50}ms` }}
            />
          ))}
        </div>
      )}
      {settledGroups.length > 0 && (
        <div className="space-y-3 pt-2">
          <h2 className="text-lg font-medium text-white/90">Payment History</h2>
          {settledGroups.map((group) => (
            <PaymentHistoryItem
              key={group.id}
              group={group}
              canDelete={group.created_by === user?.id}
              onDeleted={(gid) =>
                setGroups((prev) => prev.filter((g) => g.id !== gid))
              }
            />
          ))}
        </div>
      )}
      <div className="glass p-4 space-y-3">
        <p className="text-[13px] font-medium text-white/55">Join a group</p>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Paste invite link or token"
            value={joinInput}
            onChange={(e) => setJoinInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleJoin()}
            className="min-w-0 flex-1 rounded-xl bg-white/10 px-3 py-2 text-[14px] text-white placeholder-white/30 outline-none"
          />
          <button
            onClick={handleJoin}
            disabled={!joinInput.trim()}
            className="shrink-0 rounded-xl bg-violet-500 px-4 py-2 text-[14px] font-medium text-white transition-opacity hover:opacity-80 disabled:opacity-40"
          >
            Join
          </button>
        </div>
      </div>

      <Link to="/groups/new" aria-label="Create new group" className="fab">
        +
      </Link>
    </div>
  );
}
