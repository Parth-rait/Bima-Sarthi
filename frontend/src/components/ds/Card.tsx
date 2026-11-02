import type { ElementType, HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const TONES = {
  /** a paper sheet lifted slightly off the ground: one hairline, one soft shadow */
  sheet: "border border-line bg-paper text-ink shadow-sheet",
  /** a flat pale-peach panel: no border, no shadow (secondary content) */
  slip: "bg-peach text-ink",
  /** a raised surface on the ink band */
  ink: "bg-ink-raised text-on-ink",
  /** 3a alias of `ink` */
  night: "bg-ink-raised text-on-ink",
  plain: "bg-transparent",
} as const;

/**
 * Use sparingly: most grouping is done by bands, columns and hairlines, not boxes. Never nest a Card in a Card.
 */
export function Card({
  as,
  tone = "sheet",
  className,
  ...rest
}: HTMLAttributes<HTMLElement> & { as?: ElementType; tone?: keyof typeof TONES }) {
  const Tag = (as ?? "div") as ElementType;
  return <Tag className={cn("rounded-card p-5 md:p-6", TONES[tone], className)} {...rest} />;
}
