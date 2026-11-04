import type { ReactNode } from "react";
import { BorderTrail, GlowEffect, Magnetic } from "@/components/ui/motion-primitives";

/**
 * The one action on a screen, made to be noticed (motion-primitives: Magnetic + GlowEffect + BorderTrail).
 * Wraps exactly one button. The glow and the trail go quiet while that button is disabled or busy (claim.css),
 * so a light never invites a click that cannot happen. Reduced motion: the glow is still, nothing moves.
 * Colours are tokens, never hex: action indigo, lavender, saffron.
 */
export function Spark({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <span className={`spark ${className}`}>
      <Magnetic intensity={0.25} range={120}>
        <span className="spark-body">
          <GlowEffect
            className="spark-glow"
            // inline so it beats the primitive's inset-0 utility; route.css sets --spark-spread per size
            style={{ inset: "var(--spark-spread, -10px)", width: "auto", height: "auto" }}
            mode="rotate"
            blur={18}
            duration={6}
            colors={["var(--color-action)", "var(--color-dusty-rose)", "var(--color-apricot)", "var(--color-sky-blue)", "var(--color-action)"]}
          />
          {children}
          <BorderTrail className="spark-trail" size={56} thickness={2} transition={{ repeat: Infinity, duration: 4.5, ease: "linear" }} />
        </span>
      </Magnetic>
    </span>
  );
}
