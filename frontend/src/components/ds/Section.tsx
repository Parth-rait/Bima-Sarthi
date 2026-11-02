import type { ElementType, HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

/*
 * LAYOUT PRIMITIVES (phase 3a). Vocabulary, also documented in DESIGN.md:
 *   Band   full-bleed background wrapper            data-layout="band"  data-tone="ivory|peach|sky|ink"  data-pad="tight|none"
 *   Wrap   the content well inside a band           data-layout="wrap"  data-wrap="wide|default|narrow"
 *   Prose  running text, max ~68ch                  data-layout="prose"
 *   Grid12 a 12-column grid (span with col-span-*)  data-layout="grid-12"
 * The CSS lives in styles/layout.css; widths and gutters are tokens in styles/tokens.css.
 */
export type BandTone = "ivory" | "peach" | "sky" | "ink";
export type WrapWidth = "wide" | "default" | "narrow";

/** A full-bleed band. Pass `labelledBy` the id of its heading. Compose with <Wrap>. */
export function Band({
  tone = "ivory",
  pad,
  as,
  labelledBy,
  className,
  children,
  ...rest
}: Omit<HTMLAttributes<HTMLElement>, "children"> & { tone?: BandTone; pad?: "tight" | "none"; as?: ElementType; labelledBy?: string; children?: ReactNode }) {
  const Tag = (as ?? "section") as ElementType;
  return (
    <Tag data-layout="band" data-tone={tone} data-pad={pad} aria-labelledby={labelledBy} className={cn("band", tone === "ink" && "on-ink", className)} {...rest}>
      {children}
    </Tag>
  );
}

/** The content well: `wide` ~1440px (navbar, heroes), `default` ~1280px, `narrow` ~960px (forms, prose pages). Never touches the screen edge. */
export function Wrap({ width = "default", className, ...rest }: HTMLAttributes<HTMLDivElement> & { width?: WrapWidth }) {
  return <div data-layout="wrap" data-wrap={width} className={cn("wrap", className)} {...rest} />;
}

/** Running text: a comfortable measure (~68ch). Use inside a column, not as a page-level box. */
export function Prose({ as, className, ...rest }: HTMLAttributes<HTMLElement> & { as?: ElementType }) {
  const Tag = (as ?? "div") as ElementType;
  return <Tag data-layout="prose" className={cn("prose-measure", className)} {...rest} />;
}

/** A 12-column grid. Children span with Tailwind: `lg:col-span-6`, `lg:col-start-8`, ... (full width below `lg` by default). */
export function Grid12({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div data-layout="grid-12" className={cn("grid-12", className)} {...rest} />;
}

/* ---- legacy API (kept so unported pages compile). Agent 3b: migrate to Band + Wrap, then delete both. ---- */
const LEGACY_TONES = { ivory: "ivory", champagne: "peach", cream: "ivory", night: "ink", wine: "ink" } as const;

/** @deprecated use <Wrap>. Now the `default` well. */
export function Container({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <Wrap width="default" className={className} {...rest} />;
}

/** @deprecated use <Band> + <Wrap>. */
export function Section({
  tone = "ivory",
  labelledBy,
  className,
  innerClassName,
  children,
  ...rest
}: Omit<HTMLAttributes<HTMLElement>, "children"> & { tone?: keyof typeof LEGACY_TONES; labelledBy?: string; innerClassName?: string; children: ReactNode }) {
  return (
    <Band tone={LEGACY_TONES[tone]} labelledBy={labelledBy} className={className} {...rest}>
      <Wrap width="default" className={innerClassName}>
        {children}
      </Wrap>
    </Band>
  );
}
