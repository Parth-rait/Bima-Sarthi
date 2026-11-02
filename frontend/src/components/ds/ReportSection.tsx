import { useId, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/** A titled block of a report or plan, with an optional "where this comes from" line. */
export function ReportSection({
  title,
  source,
  children,
  level = 2,
  className,
  id,
}: {
  title: ReactNode;
  source?: ReactNode;
  children: ReactNode;
  level?: 2 | 3;
  className?: string;
  id?: string;
}) {
  const hid = useId();
  const H = `h${level}` as "h2" | "h3";
  return (
    <section id={id} aria-labelledby={hid} className={cn("print-keep border-t border-line pt-8 first:border-t-0 first:pt-0", className)}>
      <H id={hid} className="m-0 font-display text-h3 font-medium text-ink">
        {title}
      </H>
      {source ? <p className="mt-1 mb-0 text-meta text-ink-soft">{source}</p> : null}
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  );
}
