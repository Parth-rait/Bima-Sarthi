import { cva, type VariantProps } from "class-variance-authority";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";
import { Link, type LinkProps } from "react-router";
import { cn } from "@/lib/utils";
import { Loader } from "./Loader";

/**
 * One button for the whole product. The ONE primary action colour is indigo (--color-action) with porcelain text; on hover/press
 * it turns saffron (the apricot token) with ink text, which is apricot's only job besides key highlights. States: hover,
 * focus-visible (3px ink ring, ivory on ink bands), pressed (1px down), disabled (receded surface + not-allowed
 * cursor, never a smudge pattern), loading (spinner + aria-busy). 44px minimum height on every size.
 */
export const buttonStyles = cva(
  [
    "relative inline-flex min-h-11 items-center justify-center gap-2 rounded-ctl border px-6 py-2 text-base font-semibold no-underline",
    "transition-[background-color,color,border-color,transform] duration-150 ease-out motion-reduce:transition-none",
    "active:translate-y-px motion-reduce:active:translate-y-0 cursor-pointer select-none",
    "disabled:cursor-not-allowed aria-disabled:cursor-not-allowed",
    // disabled recedes instead of smudging: the surface drops to peach and the text to ink-soft (6.4:1, still
    // readable), the border thins, and the cursor says what colour may not. No opacity fade, no hatch pattern.
    "disabled:border-line disabled:bg-peach disabled:text-ink-soft disabled:shadow-none aria-disabled:border-line aria-disabled:bg-peach aria-disabled:text-ink-soft aria-disabled:shadow-none",
  ],
  {
    variants: {
      variant: {
        primary: "border-action bg-action text-on-ink shadow-[inset_0_1px_0_rgb(255_255_255/0.18),0_8px_20px_-10px_rgb(52_49_138/0.7)] hover:border-apricot hover:bg-apricot hover:text-ink active:bg-apricot-soft",
        secondary: "border-ink bg-transparent text-ink hover:bg-peach-deep",
        quiet: "border-transparent bg-transparent px-2 text-ink underline decoration-gold decoration-2 underline-offset-4 hover:bg-peach",
        danger: "border-terracotta bg-transparent text-terracotta-ink hover:bg-terracotta-wash",
        // on an ink band: ivory fill, ink text (13.8:1); apricot on hover
        onInk: "border-on-ink bg-on-ink text-ink hover:border-apricot hover:bg-apricot",
        onInkQuiet: "border-on-ink-soft bg-transparent text-on-ink hover:bg-ink-raised",
        // 3a aliases (old names); delete once no page uses them
        onNight: "border-on-ink bg-on-ink text-ink hover:border-apricot hover:bg-apricot",
        onNightQuiet: "border-on-ink-soft bg-transparent text-on-ink hover:bg-ink-raised",
      },
      size: { md: "", lg: "min-h-12 px-7 text-[1.0625rem]", sm: "px-4 text-control" },
      block: { true: "w-full", false: "" },
    },
    defaultVariants: { variant: "primary", size: "md", block: false },
  },
);

type Common = VariantProps<typeof buttonStyles> & { loading?: boolean; loadingLabel?: string; children?: ReactNode; className?: string };

type AsButton = Common & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "children"> & { to?: undefined; href?: undefined };
type AsRouterLink = Common & Omit<LinkProps, "className" | "children" | "to"> & { to: LinkProps["to"]; href?: undefined };
type AsAnchor = Common & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "className" | "children"> & { href: string; to?: undefined };

export type ButtonProps = AsButton | AsRouterLink | AsAnchor;

export function Button(props: ButtonProps) {
  const { variant, size, block, loading, loadingLabel, children, className, ...rest } = props as Common & Record<string, unknown>;
  const cls = cn(buttonStyles({ variant, size, block }), className);
  const body = (
    <>
      {loading ? <Loader size={18} label={loadingLabel} inline /> : null}
      {children}
    </>
  );
  if ("to" in rest && rest.to !== undefined) {
    const { to, ...linkRest } = rest as unknown as LinkProps;
    return (
      <Link to={to} className={cls} {...linkRest}>
        {body}
      </Link>
    );
  }
  if ("href" in rest && rest.href !== undefined) {
    return (
      <a className={cls} {...(rest as AnchorHTMLAttributes<HTMLAnchorElement>)}>
        {body}
      </a>
    );
  }
  const { type = "button", disabled, ...btn } = rest as ButtonHTMLAttributes<HTMLButtonElement>;
  return (
    <button type={type} className={cls} disabled={disabled || loading} aria-busy={loading || undefined} {...btn}>
      {body}
    </button>
  );
}
