import { useEffect, useState } from 'react';
import api from '../api/axios';
import ErrorMessage from '../components/ErrorMessage';
import { SkeletonList } from '../components/LoadingSpinner';
import useAuthStore from '../store/authStore';
import PaymentHistoryItem from '../components/PaymentHistoryItem';

export default function PaymentHistoryPage() {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    api
      .get('/groups/')
      .then(({ data }) => setGroups(data))
      .catch((err) =>
        setError(err.response?.data?.detail || 'Failed to load history')
      )
      .finally(() => setLoading(false));
  }, []);

  const settledGroups = groups.filter((g) => g.settled_at);

  return (
    <div className="space-y-4">
      <h1 className="text-[28px] font-semibold text-white">Payment History</h1>
      <ErrorMessage message={error} />
      {loading ? (
        <SkeletonList count={3} />
      ) : settledGroups.length === 0 ? (
        <div className="rounded-glass border border-dashed border-white/15 bg-white/[0.03] p-8 text-center">
          <p className="text-[15px] text-white/55">No settled groups yet.</p>
        </div>
      ) : (
        <div className="space-y-3">
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
    </div>
  );
}
