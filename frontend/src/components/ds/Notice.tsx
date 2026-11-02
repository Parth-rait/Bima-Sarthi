import type { ReactNode, Ref } from "react";
import { IconAlert, IconInfo } from "@/components/icons";
import { cn } from "@/lib/utils";

export type NoticeTone = "error" | "warn" | "info" | "ok";

const TONE: Record<NoticeTone, string> = {
  error: "bg-terracotta-wash text-ink",
  warn: "bg-amber-wash text-ink",
  info: "bg-peach text-ink",
  ok: "bg-sage-wash text-ink",
};
const TITLE: Record<NoticeTone, string> = {
  error: "text-terracotta-ink",
  warn: "text-amber-ink",
  info: "text-ink",
  ok: "text-sage-ink",
};

/**
 * One inline message: a tinted wash (no border), a glyph and a bold title, then the words. Colour only reinforces:
 * errors and warnings carry the triangle, information the circle-i. `role="alert"` for errors (pass `boxRef` to move focus to it),
 * `role="status"` otherwise. Use it for what happened, why, and what to do; never as a card for ordinary content.
 */
export function Notice({
  tone = "info",
  title,
  children,
  role,
  boxRef,
  className,
  live,
}: {
  tone?: NoticeTone;
  title?: ReactNode;
  children?: ReactNode;
  role?: "alert" | "status" | "note";
  boxRef?: Ref<HTMLDivElement>;
  className?: string;
  live?: boolean;
}) {
  const r = role ?? (tone === "error" ? "alert" : live ? "status" : undefined);
  return (
    <div role={r} tabIndex={tone === "error" ? -1 : undefined} ref={boxRef} className={cn("rounded-ctl px-4 py-3 md:px-5 md:py-4", TONE[tone], className)}>
      {title ? (
        <p className={cn("m-0 flex items-center gap-2 font-bold", TITLE[tone])}>
          {tone === "error" || tone === "warn" ? <IconAlert size={20} className="shrink-0" /> : <IconInfo size={20} className="shrink-0" />}
          <span>{title}</span>
        </p>
      ) : null}
      {children ? <div className={cn("space-y-2", title && "mt-1.5")}>{children}</div> : null}
    </div>
  );
}
