import { Link } from 'react-router-dom';

export default function GroupCard({ group, style }) {
  return (
    <Link
      to={`/groups/${group.id}`}
      style={style}
      className="card stagger-item block p-4 transition-colors hover:border-rule-strong"
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-base font-semibold text-ink">{group.name}</h3>
        <span className="shrink-0 rounded-pill border border-rule px-2.5 py-0.5 text-xs font-medium text-muted">
          {group.member_count} {group.member_count === 1 ? 'member' : 'members'}
        </span>
      </div>
      {group.description && (
        <p className="mt-1 line-clamp-2 text-[15px] text-ink-soft">
          {group.description}
        </p>
      )}
      <div className="mt-2 flex items-center justify-between gap-3">
        <p className="text-[13px] text-muted">
          Created {new Date(group.created_at).toLocaleDateString()}
        </p>
        {typeof group.my_balance === 'number' && (
          <p
            className={`shrink-0 text-[13px] tabular-nums ${
              Math.abs(group.my_balance) < 0.005
                ? 'text-muted'
                : 'font-semibold text-ink'
            }`}
          >
            {Math.abs(group.my_balance) < 0.005
              ? 'Settled up'
              : group.my_balance > 0
                ? `You're owed $${group.my_balance.toFixed(2)}`
                : `You owe $${Math.abs(group.my_balance).toFixed(2)}`}
          </p>
        )}
      </div>
    </Link>
  );
}
