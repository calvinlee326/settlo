const VARIANTS = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  accent: 'btn-accent',
  danger: 'btn-danger',
};

export default function Button({
  variant = 'primary',
  className = '',
  children,
  ...props
}) {
  return (
    <button className={`btn ${VARIANTS[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}
