import type { ReactNode, Ref } from "react";
import { cn } from "@/lib/utils";

/**
 * An error that explains itself: what happened, why (when known), and what to do next.
 * role="alert" so it is announced; pass `boxRef` to move focus to it.
 * The outline is dashed-and-solid by variant, so it is never colour alone: a heading word and an icon say "problem".
 */
export function ErrorState({
  title,
  what,
  why,
  next,
  children,
  boxRef,
  className,
  pageHeading = false,
}: {
  title: string;
  what: ReactNode;
  why?: ReactNode;
  next?: ReactNode;
  children?: ReactNode;
  boxRef?: Ref<HTMLDivElement>;
  className?: string;
  /** Render the title as the page's <h1> (focus target on navigation). */
  pageHeading?: boolean;
}) {
  const Title = pageHeading ? "h1" : "p";
  return (
    <div role="alert" tabIndex={-1} ref={boxRef} className={cn("rounded-ctl border-2 border-terracotta bg-terracotta-wash p-5 text-terracotta-ink", className)}>
      <Title {...(pageHeading ? { tabIndex: -1, "data-page-heading": true } : {})} className="m-0 flex items-center gap-2 text-base font-bold">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
          <path d="M12 3.5 21 19.5H3L12 3.5Z" />
          <path d="M12 10v4.5M12 17.2v.01" />
        </svg>
        {title}
      </Title>
      <p className="mt-2 mb-0">{what}</p>
      {why ? <p className="mt-2 mb-0">{why}</p> : null}
      {next ? <p className="mt-2 mb-0 font-semibold">{next}</p> : null}
      {children ? <div className="mt-4 flex flex-wrap gap-3">{children}</div> : null}
    </div>
  );
}
