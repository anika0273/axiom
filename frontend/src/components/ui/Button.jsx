import { clsx } from 'clsx'
import LoadingSpinner from './LoadingSpinner'

/**
 * Button with multiple variants, sizes, and a loading state.
 * @param {Object} props
 * @param {'primary'|'secondary'|'ghost'|'danger'} [props.variant='primary']
 * @param {'sm'|'md'|'lg'} [props.size='md']
 * @param {boolean} [props.loading=false]
 * @param {boolean} [props.disabled=false]
 * @param {string} [props.className]
 */
export default function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  children,
  className,
  ...props
}) {
  const base = [
    'inline-flex items-center justify-center rounded-md font-medium',
    'transition-all duration-150 ease-in-out select-none',
    'focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1',
    'focus-visible:ring-offset-deep',
  ]

  const variants = {
    primary: [
      'bg-blue text-white focus-visible:ring-blue',
      'hover:brightness-110 shadow-glow hover:shadow-glow-lg',
    ],
    secondary: [
      'bg-elevated border border-subtle text-primary focus-visible:ring-active',
      'hover:bg-hover hover:border-active',
    ],
    ghost: [
      'text-secondary focus-visible:ring-subtle',
      'hover:text-primary hover:bg-hover',
    ],
    danger: [
      'bg-red text-white focus-visible:ring-red',
      'hover:brightness-110',
    ],
  }

  const sizes = {
    sm: 'h-7 px-3 text-xs gap-1.5',
    md: 'h-9 px-4 text-sm gap-2',
    lg: 'h-11 px-6 text-[15px] gap-2.5',
  }

  const spinnerSize = { sm: 12, md: 14, lg: 16 }

  return (
    <button
      className={clsx(
        base,
        variants[variant],
        sizes[size],
        (loading || disabled) && 'opacity-50 cursor-not-allowed pointer-events-none',
        className,
      )}
      disabled={loading || disabled}
      {...props}
    >
      {loading && <LoadingSpinner size={spinnerSize[size]} />}
      {children}
    </button>
  )
}
