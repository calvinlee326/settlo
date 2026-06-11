import Avatar from './Avatar';

export default function ExpenseItem({ expense, canDelete, onDelete }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <Avatar name={expense.paid_by_username || '?'} size="sm" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-slate-900">
          {expense.title}
        </p>
        <p className="text-xs text-slate-500">
          Paid by {expense.paid_by_username || 'Unknown'} ·{' '}
          {new Date(expense.created_at).toLocaleDateString()}
        </p>
      </div>
      <div className="text-right">
        <p className="text-sm font-bold text-slate-900">
          ${expense.amount.toFixed(2)}
        </p>
        <p className="text-xs text-slate-400">
          {expense.split_type === 'EQUAL' ? 'Split equally' : 'Custom split'}
        </p>
      </div>
      {canDelete && (
        <button
          onClick={onDelete}
          aria-label="Delete expense"
          className="ml-1 text-slate-300 hover:text-red-500"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      )}
    </div>
  );
}
