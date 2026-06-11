import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import api from '../api/axios';
import ErrorMessage from '../components/ErrorMessage';
import LoadingSpinner from '../components/LoadingSpinner';
import SettlementItem from '../components/SettlementItem';

export default function SettlementPage() {
  const { id } = useParams();
  const [balances, setBalances] = useState([]);
  const [settlements, setSettlements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [payingId, setPayingId] = useState(null);
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

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-900">Settle Up</h1>
        <Link
          to={`/groups/${id}`}
          className="text-sm font-medium text-primary-600 hover:underline"
        >
          Back to group
        </Link>
      </div>

      <ErrorMessage message={error} />

      <div className="rounded-2xl bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-700">Balances</h2>
        <div className="mt-3 space-y-2">
          {balances.map((b) => (
            <div
              key={b.user_id}
              className="flex items-center justify-between text-sm"
            >
              <span className="text-slate-600">{b.username || 'Unknown'}</span>
              <span
                className={`font-semibold ${
                  b.balance > 0.004
                    ? 'text-emerald-600'
                    : b.balance < -0.004
                      ? 'text-red-600'
                      : 'text-slate-400'
                }`}
              >
                {b.balance > 0.004 ? '+' : ''}
                ${b.balance.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      </div>

      <h2 className="text-base font-semibold text-slate-900">Payments</h2>
      {settlements.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
          <p className="text-sm text-slate-500">
            All settled up! Nobody owes anything.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {settlements.map((settlement) => (
            <SettlementItem
              key={settlement.id}
              settlement={settlement}
              paying={payingId === settlement.id}
              onPay={() => handlePay(settlement.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
