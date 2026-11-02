import { cn } from "@/lib/utils";

/**
 * A spinner for work that is really happening. Under prefers-reduced-motion it stops spinning and the
 * label carries the meaning. `inline` hides it from assistive tech (the parent button already has aria-busy).
 */
export function Loader({ label, size = 24, inline = false, className }: { label?: string; size?: number; inline?: boolean; className?: string }) {
  const ring = (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" className={cn("animate-spin motion-reduce:animate-none", className)}>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
  if (inline) return ring;
  return (
    <span role="status" className="inline-flex items-center gap-3 text-ink-soft">
      {ring}
      {label ? <span>{label}</span> : <span className="sr-only">Loading</span>}
    </span>
  );
}
