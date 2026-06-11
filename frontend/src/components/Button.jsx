const VARIANTS = {
  primary:
    'bg-primary-600 text-white hover:bg-primary-700 disabled:bg-primary-600/50',
  secondary:
    'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 disabled:opacity-50',
  danger: 'bg-red-600 text-white hover:bg-red-700 disabled:bg-red-600/50',
};

export default function Button({
  variant = 'primary',
  className = '',
  children,
  ...props
}) {
  return (
    <button
      className={`rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
