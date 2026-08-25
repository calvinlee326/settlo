import { useState } from 'react';
import api from '../api/axios';
import SettlementItem from './SettlementItem';

export default function PaymentHistoryItem({ group, canDelete, onDeleted }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && !detail) {
      setLoading(true);
      try {
        const [expensesRes, settleRes] = await Promise.all([
          api.get(`/groups/${group.id}/expenses/`),
          api.get(`/groups/${group.id}/settlements/`),
        ]);
        setDetail({
          expenses: expensesRes.data,
          settlements: settleRes.data.paid_settlements ?? [],
        });
      } catch {
        setDetail({ expenses: [], settlements: [] });
      } finally {
        setLoading(false);
      }
    }
  };

  const handleDelete = async (e) => {
    e.stopPropagation();
    if (!window.confirm('Remove this from payment history?')) return;
    setDeleting(true);
    try {
      await api.delete(`/groups/${group.id}`);
      onDeleted(group.id);
    } catch {
      setDeleting(false);
    }
  };

  return (
    <div className="card overflow-hidden">
      <button
        onClick={toggle}
        className="flex w-full items-center justify-between p-4 text-left"
      >
        <div>
          <p className="text-[15px] font-semibold text-ink">{group.name}</p>
          <p className="text-[13px] text-muted">
            Settled {new Date(group.settled_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[15px] font-semibold tabular-nums text-ink-soft">
            ${(group.total ?? 0).toFixed(2)}
          </span>
          <span className="text-muted">{open ? '▾' : '▸'}</span>
        </div>
      </button>

      {open && (
        <div className="space-y-4 border-t border-rule p-4">
          {loading || !detail ? (
            <p className="text-[14px] text-muted">Loading…</p>
          ) : (
            <>
              <div>
                <h4 className="eyebrow">
                  Expenses
                </h4>
                <div className="mt-2 space-y-1">
                  {detail.expenses.map((e) => (
                    <div
                      key={e.id}
                      className="flex items-center justify-between text-[14px]"
                    >
                      <span className="text-ink">
                        {e.title}
                        <span className="text-muted">
                          {' '}· {e.paid_by_username || 'Someone'}
                        </span>
                      </span>
                      <span className="tabular-nums text-ink-soft">
                        ${e.amount.toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {detail.settlements.length > 0 && (
                <div>
                  <h4 className="eyebrow">
                    Settlement
                  </h4>
                  <div className="mt-2 space-y-2">
                    {detail.settlements.map((s) => (
                      <SettlementItem
                        key={s.id}
                        settlement={s}
                        paying={false}
                        onPay={null}
                      />
                    ))}
                  </div>
                </div>
              )}

              {canDelete && (
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  className="text-[13px] font-medium text-ink transition-colors hover:underline disabled:opacity-40"
                >
                  {deleting ? 'Removing…' : 'Remove from history'}
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
