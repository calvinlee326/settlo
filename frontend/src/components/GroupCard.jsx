import { Link } from 'react-router-dom';

export default function GroupCard({ group, style }) {
  return (
    <Link
      to={`/groups/${group.id}`}
      style={style}
      className="glass stagger-item block p-5 transition-all duration-300 ease-spring hover:-translate-y-1 hover:border-white/25 hover:shadow-[0_14px_44px_rgba(0,0,0,0.45)]"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-white/90">{group.name}</h3>
        <span className="rounded-pill border border-white/15 bg-white/10 px-2.5 py-0.5 text-xs font-medium text-white/75">
          {group.member_count} {group.member_count === 1 ? 'member' : 'members'}
        </span>
      </div>
      {group.description && (
        <p className="mt-1 line-clamp-2 text-[15px] text-white/55">
          {group.description}
        </p>
      )}
      <p className="mt-2 text-[13px] text-white/30">
        Created {new Date(group.created_at).toLocaleDateString()}
      </p>
    </Link>
  );
}
