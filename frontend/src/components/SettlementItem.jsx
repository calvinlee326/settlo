import Avatar from './Avatar';
import Button from './Button';

export default function SettlementItem({ settlement, onPay, paying, style }) {
  return (
    <div
      style={style}
      className={`stagger-item relative flex items-center gap-3 overflow-hidden rounded-2xl border p-4 pl-5 transition-colors ${
        settlement.is_paid
          ? 'border-emerald-400/30 bg-emerald-500/10'
          : 'border-white/10 bg-white/[0.04] hover:bg-white/[0.07]'
      }`}
    >
      {!settlement.is_paid && <span className="accent-line" />}
      <div className="flex items-center -space-x-2">
        <Avatar name={settlement.from_username || '?'} size="sm" />
        <Avatar name={settlement.to_username || '?'} size="sm" />
      </div>
      <div className="min-w-0 flex-1">
        <p
          className={`text-[15px] ${
            settlement.is_paid ? 'text-white/50 line-through' : 'text-white/90'
          }`}
        >
          <span className="font-semibold">
            {settlement.from_username || 'Someone'}
          </span>{' '}
          pays{' '}
          <span className="font-semibold">
            {settlement.to_username || 'someone'}
          </span>
        </p>
        <p
          className={`text-lg font-bold tabular-nums ${
            settlement.is_paid
              ? 'text-emerald-300/70 line-through'
              : 'bg-gradient-to-r from-violet-400 to-sky-400 bg-clip-text text-transparent'
          }`}
        >
          ${settlement.amount.toFixed(2)}
        </p>
      </div>
      {settlement.is_paid ? (
        <span className="flex items-center gap-1 rounded-pill border border-emerald-400/40 bg-emerald-500/20 px-3 py-1 text-xs font-semibold text-emerald-300">
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          Paid
        </span>
      ) : onPay ? (
        <Button
          onClick={onPay}
          disabled={paying}
          className="shrink-0 px-4 text-sm"
        >
          {paying ? 'Saving…' : 'Mark as Paid'}
        </Button>
      ) : null}
    </div>
  );
}
