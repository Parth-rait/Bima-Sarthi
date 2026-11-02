import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Nothing here yet, and a way forward. Never a dead end. */
export function EmptyState({ title, children, art, className, headingLevel = 2, pageHeading = false }: { title: string; children?: ReactNode; art?: ReactNode; className?: string; headingLevel?: 2 | 3; pageHeading?: boolean }) {
  const H = (pageHeading ? "h1" : `h${headingLevel}`) as "h1" | "h2" | "h3";
  return (
    <div className={cn("grid items-center gap-8 rounded-card bg-peach p-6 md:grid-cols-[1fr_auto] md:p-10", className)}>
      <div>
        <H {...(pageHeading ? { tabIndex: -1, "data-page-heading": true } : {})} className="m-0 font-display text-h3 font-medium text-ink">
          {title}
        </H>
        <div className="mt-3 max-w-prose space-y-3">{children}</div>
      </div>
      {art ? <div className="hidden md:block">{art}</div> : null}
    </div>
  );
}
