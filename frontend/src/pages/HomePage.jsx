import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/axios';
import ErrorMessage from '../components/ErrorMessage';
import GroupCard from '../components/GroupCard';
import { SkeletonList } from '../components/LoadingSpinner';

export default function HomePage() {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

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
      <Link to="/groups/new" aria-label="Create new group" className="fab">
        +
      </Link>
    </div>
  );
}
