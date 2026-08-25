import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import api from '../api/axios';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import { SkeletonList } from '../components/LoadingSpinner';
import SettlementItem from '../components/SettlementItem';

export default function SettlementPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [balances, setBalances] = useState([]);
  const [settlements, setSettlements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const { data } = await api.get(`/groups/${id}/settlements/`);
      setBalances(data.balances);
      setSettlements(data.settlements);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load settlements');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const handleConfirm = async () => {
    setConfirming(true);
    setError('');
    try {
      await api.post(`/groups/${id}/settlements/confirm`);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to settle');
      setConfirming(false);
    }
  };

  if (loading) return <SkeletonList count={3} />;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-[28px] font-semibold text-ink">Settle Up</h1>
        <Link
          to={`/groups/${id}`}
          className="text-sm font-medium text-slate-deep transition-colors hover:text-slate-deep"
        >
          Back to group
        </Link>
      </div>

      <ErrorMessage message={error} />

      <div className="card p-5">
        <h2 className="text-[13px] font-medium uppercase tracking-wide text-muted">
          Balances
        </h2>
        <div className="mt-3 space-y-2">
          {balances.map((b) => (
            <div
              key={b.user_id}
              className="flex items-center justify-between text-[15px]"
            >
              <span className="text-ink-soft">{b.username || 'Unknown'}</span>
              <span
                className={`font-semibold tabular-nums ${
                  b.balance > 0.004
                    ? 'text-moss'
                    : b.balance < -0.004
                      ? 'text-clay'
                      : 'text-muted'
                }`}
              >
                {b.balance > 0.004 ? '+' : b.balance < -0.004 ? '-' : ''}$
                {Math.abs(b.balance).toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      </div>

      <h2 className="text-lg font-medium text-ink">Who pays whom</h2>
      {settlements.length === 0 ? (
        <div className="rounded-card border border-dashed border-rule bg-surface p-8 text-center">
          <p className="text-[15px] text-muted">
            All even — nobody owes anything.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {settlements.map((settlement, i) => (
            <SettlementItem
              key={settlement.id}
              settlement={settlement}
              style={{ animationDelay: `${i * 50}ms` }}
              paying={false}
              onPay={null}
            />
          ))}
        </div>
      )}

      <Button
        variant="primary"
        className="w-full"
        onClick={handleConfirm}
        disabled={confirming}
      >
        {confirming ? 'Settling…' : 'Confirm & settle'}
      </Button>
    </div>
  );
}
