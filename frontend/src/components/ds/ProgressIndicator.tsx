import { cn } from "@/lib/utils";

/**
 * A real measurement, nothing decorative. Give `value` (0-100) for a determinate bar (for example, the share of the
 * 25 MB upload allowance already used); leave it out for an indeterminate "working" bar, which is honest about not knowing.
 */
export function ProgressIndicator({ value, label, valueText, className }: { value?: number; label: string; valueText?: string; className?: string }) {
  const determinate = typeof value === "number";
  const pct = determinate ? Math.max(0, Math.min(100, value)) : undefined;
  return (
    <div className={className}>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={determinate ? 0 : undefined}
        aria-valuemax={determinate ? 100 : undefined}
        aria-valuenow={pct}
        aria-valuetext={valueText}
        className="h-2.5 w-full overflow-hidden rounded-full border border-line-strong bg-peach"
      >
        <div
          className={cn("h-full bg-ink", determinate ? "transition-[width] duration-300 motion-reduce:transition-none" : "w-1/3 animate-[progress-slide_1.4s_ease-in-out_infinite] motion-reduce:w-full motion-reduce:animate-none motion-reduce:opacity-40")}
          style={determinate ? { width: `${pct}%` } : undefined}
        />
      </div>
    </div>
  );
}
