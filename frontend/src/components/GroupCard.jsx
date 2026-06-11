import { Link } from 'react-router-dom';

export default function GroupCard({ group }) {
  return (
    <Link
      to={`/groups/${group.id}`}
      className="block rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-primary-500 hover:shadow"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-slate-900">{group.name}</h3>
        <span className="rounded-full bg-primary-50 px-2.5 py-0.5 text-xs font-medium text-primary-700">
          {group.member_count} {group.member_count === 1 ? 'member' : 'members'}
        </span>
      </div>
      {group.description && (
        <p className="mt-1 line-clamp-2 text-sm text-slate-500">
          {group.description}
        </p>
      )}
      <p className="mt-2 text-xs text-slate-400">
        Created {new Date(group.created_at).toLocaleDateString()}
      </p>
    </Link>
  );
}
