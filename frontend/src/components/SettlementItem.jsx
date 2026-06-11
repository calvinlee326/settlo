import Avatar from './Avatar';
import Button from './Button';

export default function SettlementItem({ settlement, onPay, paying }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center -space-x-2">
        <Avatar name={settlement.from_username || '?'} size="sm" />
        <Avatar name={settlement.to_username || '?'} size="sm" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-slate-900">
          <span className="font-semibold">
            {settlement.from_username || 'Someone'}
          </span>{' '}
          pays{' '}
          <span className="font-semibold">
            {settlement.to_username || 'someone'}
          </span>
        </p>
        <p className="text-lg font-bold text-primary-600">
          ${settlement.amount.toFixed(2)}
        </p>
      </div>
      {settlement.is_paid ? (
        <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
          Paid
        </span>
      ) : (
        <Button onClick={onPay} disabled={paying} className="shrink-0">
          {paying ? 'Saving…' : 'Mark as Paid'}
        </Button>
      )}
    </div>
  );
}
