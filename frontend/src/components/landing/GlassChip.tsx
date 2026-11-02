import { motion } from "motion/react";
import type { ReactNode, RefObject } from "react";
import { LiquidGlass } from "@/components/ui/liquid-glass";
import { usePrefersReducedMotion } from "@/hooks/useMedia";
import { cn } from "@/lib/utils";

/**
 * The one glass element on the page, used for a reason: a lens-framed statement that sits over the artwork and
 * bends the paper behind it. The words themselves sit on a solid ink plate inside the glass rim, so they stay
 * readable over any part of the artwork (ivory on ink, 10:1), whatever the refraction does behind.
 * It can be dragged within `constraints` (a pointer nicety; nothing depends on it). Reduced motion: no dragging.
 * Safari/Firefox get the component's own frosted fallback; prefers-reduced-transparency gets an opaque panel.
 */
export default function GlassChip({ children, constraints, className }: { children: ReactNode; constraints: RefObject<HTMLElement | null>; className?: string }) {
  const reduce = usePrefersReducedMotion();
  return (
    <motion.div
      drag={!reduce}
      dragConstraints={constraints}
      dragMomentum={false}
      dragElastic={0.1}
      whileDrag={reduce ? undefined : { scale: 1.02 }}
      className={cn("absolute z-20", !reduce && "cursor-grab active:cursor-grabbing", className)}
    >
      <LiquidGlass radius={26} bevelDepth={12} scale={34} aberration={3} frost={0.4} tint={0.1} className="shadow-stage ring-1 ring-white/20">
        <div className="m-1.5 rounded-[20px] bg-ink/90 px-4 py-3 text-on-ink">{children}</div>
      </LiquidGlass>
    </motion.div>
  );
}
