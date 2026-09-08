import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import api from '../api/axios';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import { SkeletonList } from '../components/LoadingSpinner';
import SettlementItem from '../components/SettlementItem';

// Cap the entry stagger: past this index every card animates together, so a
// long list finishes in ~550ms instead of growing 50ms per row.
const STAGGER_CAP = 4;

export default function SettlementPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [balances, setBalances] = useState([]);
  const [settlements, setSettlements] = useState([]);
  const [paidSettlements, setPaidSettlements] = useState([]);
  const [reversedSettlements, setReversedSettlements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [pendingId, setPendingId] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const { data } = await api.get(`/groups/${id}/settlements/`);
      setBalances(data.balances);
      setSettlements(data.settlements);
      setPaidSettlements(data.paid_settlements ?? []);
      setReversedSettlements(data.reversed_settlements ?? []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load settlements');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const act = async (settlementId, path, fallback) => {
    setPendingId(settlementId);
    setError('');
    try {
      await api.post(`/groups/${id}/settlements/${settlementId}/${path}`);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || fallback);
    } finally {
      setPendingId(null);
    }
  };

  const handleConfirm = async () => {
    setConfirming(true);
    setError('');
    try {
      await api.post(`/groups/${id}/settlements/confirm`);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to archive');
      setConfirming(false);
    }
  };

  if (loading) return <SkeletonList count={3} />;

  const outstanding = settlements.length;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-[28px] font-semibold text-ink">Settle Up</h1>
        <Link
          to={`/groups/${id}`}
          className="text-sm font-medium text-muted transition-colors hover:text-ink"
        >
          Back to group
        </Link>
      </div>

      <p className="rounded-card border border-rule bg-sunk p-4 text-[13px] text-muted">
        Settlo keeps track of who owes what. It does not move any money —
        pay each other however you normally do, then record it here.
      </p>

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
                className={`tabular-nums ${
                  b.balance > 0.004
                    ? 'font-bold text-ink'
                    : b.balance < -0.004
                      ? 'font-normal text-ink'
                      : 'font-normal text-muted'
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
      {outstanding === 0 ? (
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
              style={{ animationDelay: `${Math.min(i, STAGGER_CAP) * 50}ms` }}
              paying={pendingId === settlement.id}
              onPay={() =>
                act(settlement.id, 'pay', 'Failed to record this payment')
              }
            />
          ))}
        </div>
      )}

      {paidSettlements.length > 0 && (
        <>
          <h2 className="text-lg font-medium text-ink">Recorded payments</h2>
          <div className="space-y-3">
            {paidSettlements.map((settlement) => (
              <SettlementItem
                key={settlement.id}
                settlement={settlement}
                paying={pendingId === settlement.id}
                onReverse={() =>
                  act(settlement.id, 'reverse', 'Failed to undo this payment')
                }
              />
            ))}
          </div>
        </>
      )}

      {reversedSettlements.length > 0 && (
        <>
          <h2 className="text-lg font-medium text-ink">Undone payments</h2>
          <div className="space-y-2">
            {reversedSettlements.map((s) => (
              <div
                key={s.id}
                className="rounded-card border border-dashed border-rule bg-surface p-4 text-[13px] text-muted"
              >
                <span className="text-ink">
                  {s.from_username || 'Someone'} &rarr; {s.to_username || 'someone'}
                </span>{' '}
                ${s.amount.toFixed(2)} &middot; undone by{' '}
                {s.reversed_by_username || 'someone'} on{' '}
                {new Date(s.reversed_at).toLocaleDateString()}
              </div>
            ))}
          </div>
        </>
      )}

      <div className="space-y-2">
        <Button
          variant="primary"
          className="w-full"
          onClick={handleConfirm}
          disabled={confirming || outstanding > 0}
        >
          {confirming ? 'Archiving…' : 'Archive group'}
        </Button>
        <p className="text-center text-[13px] text-muted">
          {outstanding > 0
            ? `Record the ${outstanding} remaining payment${outstanding === 1 ? '' : 's'} to archive this group.`
            : 'Archiving closes the group to new expenses. Only the group creator can do this.'}
        </p>
      </div>
    </div>
  );
}
