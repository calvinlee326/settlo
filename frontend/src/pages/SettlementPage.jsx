import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import api from '../api/axios';
import ErrorMessage from '../components/ErrorMessage';
import { SkeletonList } from '../components/LoadingSpinner';
import SettlementItem from '../components/SettlementItem';

export default function SettlementPage() {
  const { id } = useParams();
  const [balances, setBalances] = useState([]);
  const [settlements, setSettlements] = useState([]);
  const [paidSettlements, setPaidSettlements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [payingId, setPayingId] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const { data } = await api.get(`/groups/${id}/settlements/`);
      setBalances(data.balances);
      setSettlements(data.settlements);
      setPaidSettlements(data.paid_settlements ?? []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load settlements');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const handlePay = async (settlementId) => {
    setPayingId(settlementId);
    setError('');
    try {
      await api.post(`/groups/${id}/settlements/${settlementId}/pay`);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to mark as paid');
    } finally {
      setPayingId(null);
    }
  };

  if (loading) return <SkeletonList count={3} />;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-[28px] font-semibold text-white">Settle Up</h1>
        <Link
          to={`/groups/${id}`}
          className="text-sm font-medium text-sky-400 transition-colors hover:text-sky-300"
        >
          Back to group
        </Link>
      </div>

      <ErrorMessage message={error} />

      <div className="glass p-5">
        <h2 className="text-[13px] font-medium uppercase tracking-wide text-white/50">
          Balances
        </h2>
        <div className="mt-3 space-y-2">
          {balances.map((b) => (
            <div
              key={b.user_id}
              className="flex items-center justify-between text-[15px]"
            >
              <span className="text-white/75">{b.username || 'Unknown'}</span>
              <span
                className={`font-semibold tabular-nums ${
                  b.balance > 0.004
                    ? 'text-emerald-400'
                    : b.balance < -0.004
                      ? 'text-red-400'
                      : 'text-white/30'
                }`}
              >
                {b.balance > 0.004 ? '+' : ''}
                ${b.balance.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      </div>

      <h2 className="text-lg font-medium text-white/90">Payments</h2>
      {settlements.length === 0 ? (
        <div className="rounded-glass border border-dashed border-white/15 bg-white/[0.03] p-8 text-center">
          <p className="text-[15px] text-white/55">
            All settled up! Nobody owes anything.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {settlements.map((settlement, i) => (
            <SettlementItem
              key={settlement.id}
              settlement={settlement}
              style={{ animationDelay: `${i * 50}ms` }}
              paying={payingId === settlement.id}
              onPay={() => handlePay(settlement.id)}
            />
          ))}
        </div>
      )}

      {paidSettlements.length > 0 && (
        <>
          <h2 className="text-lg font-medium text-white/90">Payment History</h2>
          <div className="space-y-3">
            {paidSettlements.map((settlement, i) => (
              <SettlementItem
                key={settlement.id}
                settlement={settlement}
                style={{ animationDelay: `${i * 50}ms` }}
                paying={false}
                onPay={null}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
