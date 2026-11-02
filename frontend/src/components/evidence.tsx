import { useId, type ReactNode } from "react";
import type { Verdict } from "../api";
import { useSession } from "../state/store";
import { VerdictShape } from "./icons";
import type { Key } from "../i18n";
import { cn } from "@/lib/utils";

export const controlCls =
  "min-h-11 w-full rounded-ctl border border-line-strong bg-paper px-3 py-2 text-base text-ink placeholder:text-ink-soft aria-[invalid=true]:border-2 aria-[invalid=true]:border-terracotta disabled:opacity-60";

/** A labelled field with an error line wired by aria-describedby. */
export function Field({
  label,
  hint,
  error,
  children,
  className,
}: {
  label: ReactNode;
  hint?: ReactNode;
  error?: string | null;
  className?: string;
  children: (p: { id: string; "aria-describedby"?: string; "aria-invalid"?: boolean; className: string }) => ReactNode;
}) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errId = error ? `${id}-err` : undefined;
  const describedBy = [hintId, errId].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cn("field", error && "has-error", className)}>
      <label htmlFor={id} className="mb-1 block font-semibold text-ink">
        {label}
      </label>
      {hint ? (
        <p className="hint mb-1.5 mt-0 text-[0.9375rem] text-ink-soft" id={hintId}>
          {hint}
        </p>
      ) : null}
      {children({ id, "aria-describedby": describedBy, "aria-invalid": error ? true : undefined, className: controlCls })}
      {error ? (
        <p className="field-error mb-0 mt-1.5 text-[0.9375rem] font-semibold text-terracotta-ink" id={errId}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

/**
 * Yes / No (/ Not sure) as large choice pills in a fieldset. The selected pill is filled ink AND carries a tick (never colour alone).
 * Real radio inputs underneath, so arrow keys and screen readers work.
 */
export function Choice({
  legend,
  name,
  value,
  onChange,
  options,
  error,
  className,
  legendClassName,
}: {
  legend: ReactNode;
  name: string;
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string; lang?: string }>;
  error?: string | null;
  className?: string;
  legendClassName?: string;
}) {
  const id = useId();
  return (
    <fieldset className={cn("choice m-0 min-w-0 border-0 p-0", className)} aria-describedby={error ? `${id}-err` : undefined}>
      <legend className={cn("mb-2 p-0 font-semibold text-ink", legendClassName)}>{legend}</legend>
      <div className="choice-row flex flex-wrap gap-2">
        {options.map((o) => (
          <label
            key={o.value}
            lang={o.lang}
            className="radio group relative inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-ctl border border-line-strong bg-paper px-4 py-2 font-medium text-ink transition-colors duration-150 hover:bg-peach has-[:checked]:border-ink has-[:checked]:bg-ink has-[:checked]:text-on-ink has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus-ring motion-reduce:transition-none"
          >
            <input type="radio" className="peer sr-only" name={`${name}-${id}`} value={o.value} checked={value === o.value} onChange={() => onChange(o.value)} />
            <svg aria-hidden="true" focusable="false" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="hidden shrink-0 group-has-[:checked]:block">
              <path d="m5 12.5 4.5 4.5L19 7.5" />
            </svg>
            <span>{o.label}</span>
          </label>
        ))}
      </div>
      {error ? (
        <p className="field-error mb-0 mt-1.5 text-[0.9375rem] font-semibold text-terracotta-ink" id={`${id}-err`}>
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}

/** The excerpt "slip": verbatim text from a source with its page. Text only, never markup. */
export function Quote({ children, source, className }: { children: ReactNode; source?: ReactNode; className?: string }) {
  return (
    <figure className={cn("quote print-quote m-0 max-w-[70ch] rounded-ctl bg-peach px-4 py-3", className)}>
      <blockquote className="m-0 font-quote text-[1.0625rem] leading-[1.55] text-ink">{children}</blockquote>
      {source ? <figcaption className="mt-1 text-meta text-ink-soft">{source}</figcaption> : null}
    </figure>
  );
}

const STAMP: Record<Verdict, string> = {
  CHALLENGEABLE: "bg-terracotta-wash text-terracotta-ink",
  NEED_INFO: "bg-amber-wash text-amber-ink",
  CONSISTENT: "bg-sage-wash text-sage-ink",
};

export function Stamp({ verdict, className }: { verdict: Verdict; className?: string }) {
  const { t } = useSession();
  const word = t(`vw_${verdict}` as Key);
  return (
    <span
      className={cn("stamp inline-flex items-center gap-2 rounded-ctl border-2 border-current px-3 py-1 text-[0.9375rem] font-bold uppercase leading-tight tracking-[0.07em]", STAMP[verdict], className)}
      data-verdict={verdict}
    >
      <VerdictShape verdict={verdict} />
      <span className="stamp-word">{word}</span>
    </span>
  );
}

export function RuleChip({ id }: { id: string }) {
  const { t } = useSession();
  return (
    <span className="rule-chip inline-flex items-center gap-2 rounded-ctl bg-peach px-2.5 py-1 text-[0.8125rem] text-ink-soft" title={t("rule_ref")}>
      <span className="rule-chip-label font-semibold">{t("rule_ref")}</span>
      <code className="font-mono text-ink">{id}</code>
    </span>
  );
}

/** A hairline between groups. */
export function Stitch({ className }: { className?: string }) {
  return <hr className={cn("stitch m-0 border-0 border-t border-line", className)} />;
}
