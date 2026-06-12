import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../api/axios';
import ErrorMessage from '../components/ErrorMessage';
import GroupCard from '../components/GroupCard';
import { SkeletonList } from '../components/LoadingSpinner';

export default function HomePage() {
  const navigate = useNavigate();
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [joinInput, setJoinInput] = useState('');

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

  return (
    <div className="space-y-4">
      <h1 className="text-[28px] font-semibold text-white">My Groups</h1>
      <ErrorMessage message={error} />
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
          {groups.map((group, i) => (
            <GroupCard
              key={group.id}
              group={group}
              style={{ animationDelay: `${i * 50}ms` }}
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
