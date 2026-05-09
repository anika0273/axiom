/**
 * Centered empty state with icon, heading, description, and optional CTA.
 * @param {Object} props
 * @param {React.ReactNode} props.icon - Lucide icon element
 * @param {string} props.heading
 * @param {string} props.description
 * @param {React.ReactNode} [props.action] - CTA button or link
 * @param {string} [props.className]
 */
export default function EmptyState({ icon, heading, description, action, className = '' }) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center py-16 px-8 border border-dashed border-subtle rounded-xl ${className}`}
    >
      {icon && (
        <div className="mb-4 text-muted opacity-60">
          {icon}
        </div>
      )}
      <h3 className="text-base font-display font-semibold text-secondary mb-1">{heading}</h3>
      <p className="text-sm text-muted max-w-xs leading-relaxed">{description}</p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}
