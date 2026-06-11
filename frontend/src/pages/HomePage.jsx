import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/axios';
import ErrorMessage from '../components/ErrorMessage';
import GroupCard from '../components/GroupCard';
import LoadingSpinner from '../components/LoadingSpinner';

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

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-900">My Groups</h1>
      <ErrorMessage message={error} />
      {groups.length === 0 && !error ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
          <p className="text-sm text-slate-500">
            No groups yet. Create one to start splitting bills with friends.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {groups.map((group) => (
            <GroupCard key={group.id} group={group} />
          ))}
        </div>
      )}
      <Link
        to="/groups/new"
        aria-label="Create new group"
        className="fixed bottom-6 right-6 flex h-14 w-14 items-center justify-center rounded-full bg-primary-600 text-3xl font-light text-white shadow-lg transition hover:bg-primary-700"
      >
        +
      </Link>
    </div>
  );
}
