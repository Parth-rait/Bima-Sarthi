import { useId, type InputHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export const inputStyles =
  "min-h-11 w-full rounded-ctl border border-line-strong bg-paper px-3 py-2 text-base text-ink placeholder:text-ink-soft";

/** Label above, hint between label and control, error below (linked with aria-describedby, aria-invalid on the control). */
export function TextField({
  label,
  hint,
  error,
  className,
  ...input
}: { label: ReactNode; hint?: ReactNode; error?: string | null; className?: string } & Omit<InputHTMLAttributes<HTMLInputElement>, "className">) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errId = error ? `${id}-err` : undefined;
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block font-semibold text-ink">
        {label}
      </label>
      {hint ? (
        <p id={hintId} className="mb-1 mt-0 text-control text-ink-soft">
          {hint}
        </p>
      ) : null}
      <input
        id={id}
        aria-describedby={[hintId, errId].filter(Boolean).join(" ") || undefined}
        aria-invalid={error ? true : undefined}
        className={cn(inputStyles, error && "border-2 border-terracotta")}
        {...input}
      />
      {error ? (
        <p id={errId} className="mb-0 mt-1 text-control font-semibold text-terracotta-ink">
          {error}
        </p>
      ) : null}
    </div>
  );
}
