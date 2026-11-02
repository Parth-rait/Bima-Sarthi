import { cva } from "class-variance-authority";
import type { Verdict } from "@/api";
import { BadgeGlyph, VerdictShape } from "@/components/icons";
import { useSession } from "@/state/store";
import type { Key } from "@/i18n";
import { cn } from "@/lib/utils";

const stamp = cva(
  "inline-flex items-center gap-2 rounded-ctl border-2 border-current px-3 py-1 text-[0.9375rem] font-bold uppercase leading-tight tracking-[0.07em]",
  {
    variants: {
      verdict: {
        CHALLENGEABLE: "bg-terracotta-wash text-terracotta-ink",
        NEED_INFO: "bg-amber-wash text-amber-ink",
        CONSISTENT: "bg-sage-wash text-sage-ink",
      },
    },
  },
);

/**
 * A verdict, always as shape + word (and the sentence next to it). Triangle = challengeable,
 * circle with a question mark = need info, square with a tick = consistent. Colour only reinforces.
 * The verdict words come from the rule engine; this component only displays them.
 */
export function StatusBadge({ verdict, className }: { verdict: Verdict; className?: string }) {
  const { t } = useSession();
  return (
    <span className={cn(stamp({ verdict }), className)} data-verdict={verdict}>
      <VerdictShape verdict={verdict} />
      <span>{t(`vw_${verdict}` as Key)}</span>
    </span>
  );
}

/** A neutral state tag (not a verdict): word + glyph, for "Illustrative", "Verified", "Required". `warm` = amber family. */
export function Tag({ children, tone = "plain", className }: { children: React.ReactNode; tone?: "plain" | "warm"; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-ctl px-2.5 py-0.5 text-[0.8125rem] font-semibold tracking-wide",
        tone === "plain" ? "bg-peach text-ink" : "bg-amber-wash text-amber-ink",
        className,
      )}
    >
      <span aria-hidden="true" className="inline-block size-2 rotate-45 border border-current" />
      {children}
    </span>
  );
}

export type FactState = "verified" | "pending" | "confirmed";
const FACT_CLS: Record<FactState, string> = {
  verified: "bg-sage-wash text-sage-ink",
  pending: "bg-amber-wash text-amber-ink",
  confirmed: "bg-peach text-ink",
};
/**
 * The state of one extracted fact: a word AND a glyph (square tick = Verified, diamond mark = Please confirm,
 * circled tick = You confirmed). Colour only reinforces. Not a verdict.
 */
export function FactBadge({ state, children, className }: { state: FactState; children: React.ReactNode; className?: string }) {
  return (
    <span data-state={state} className={cn("tag inline-flex items-center gap-1.5 rounded-ctl px-2.5 py-0.5 text-[0.8125rem] font-semibold", FACT_CLS[state], className)}>
      <BadgeGlyph kind={state} />
      {children}
    </span>
  );
}
