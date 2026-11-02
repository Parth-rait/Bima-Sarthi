import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Verbatim text from a source, with where it came from. The product's signature: evidence is a first-class object. Text nodes only. */
export function QuoteSlip({ children, source, className }: { children: ReactNode; source?: ReactNode; className?: string }) {
  return (
    <figure className={cn("print-quote m-0 max-w-[70ch] rounded-card bg-peach px-5 py-4", className)}>
      <blockquote className="m-0 font-quote text-[1.125rem] leading-[1.55] text-ink">{children}</blockquote>
      {source ? <figcaption className="mt-1 text-meta text-ink-soft">{source}</figcaption> : null}
    </figure>
  );
}
