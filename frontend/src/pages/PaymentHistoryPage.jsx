import useSWR from 'swr';
import ErrorMessage from '../components/ErrorMessage';
import { SkeletonList } from '../components/LoadingSpinner';
import useAuthStore from '../store/authStore';
import PaymentHistoryItem from '../components/PaymentHistoryItem';

export default function PaymentHistoryPage() {
  const { data, error: loadError, mutate } = useSWR('/groups/');
  const user = useAuthStore((s) => s.user);
  const groups = data ?? [];
  const loading = !data && !loadError;
  const error = loadError
    ? loadError.response?.data?.detail || 'Failed to load history'
    : '';

  const settledGroups = groups.filter((g) => g.settled_at);

  return (
    <div className="space-y-4">
      <h1 className="text-[28px] font-semibold text-ink">Payment History</h1>
      <ErrorMessage message={error} />
      {loading ? (
        <SkeletonList count={3} />
      ) : settledGroups.length === 0 ? (
        <div className="rounded-card border border-dashed border-rule bg-surface p-8 text-center">
          <p className="text-[15px] text-muted">No settled groups yet.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {settledGroups.map((group) => (
            <PaymentHistoryItem
              key={group.id}
              group={group}
              canDelete={group.created_by === user?.id}
              onDeleted={(gid) => mutate(groups.filter((g) => g.id !== gid))}
            />
          ))}
        </div>
      )}
    </div>
  );
}
