"use client";

/*
 * Four primitives from motion-primitives (github.com/ibelick/motion-primitives, MIT, Julien Thibeaut):
 * BorderTrail, GlowEffect, Magnetic, AnimatedNumber. Kept close to the originals; the Bima Sarthi changes are
 * listed in DESIGN.md ("Component deviations"):
 *   - every primitive reads prefers-reduced-motion and holds still (no trail, a static glow, no pull, no count-up)
 *   - colours are passed in by the caller as CSS custom properties (no hex palette baked in here)
 *   - GlowEffect keeps only the modes the product uses (rotate, breathe, static)
 *   - Magnetic ignores touch and pen, so it never fights a tap
 *   - AnimatedNumber formats with the caller's locale
 */

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { motion, useMotionValue, useReducedMotion, useSpring, useTransform, type SpringOptions, type TargetAndTransition, type Transition } from "motion/react";
import { cn } from "@/lib/utils";

/* ---------- BorderTrail: a light that runs around the parent's border ---------- */
export type BorderTrailProps = { className?: string; size?: number; transition?: Transition; style?: CSSProperties; thickness?: number };

export function BorderTrail({ className, size = 60, transition, style, thickness = 1 }: BorderTrailProps) {
  const reduce = useReducedMotion();
  if (reduce) return null;
  return (
    <span
      aria-hidden="true"
      style={{ borderWidth: thickness }}
      className="pointer-events-none absolute inset-0 rounded-[inherit] border border-transparent [mask-clip:padding-box,border-box] [mask-composite:intersect] [mask-image:linear-gradient(transparent,transparent),linear-gradient(#000,#000)]"
    >
      <motion.span
        className={cn("absolute block aspect-square", className)}
        style={{ width: size, offsetPath: `rect(0 auto auto 0 round ${size}px)`, ...style }}
        animate={{ offsetDistance: ["0%", "100%"] }}
        transition={transition ?? { repeat: Infinity, duration: 5, ease: "linear" }}
      />
    </span>
  );
}

/* ---------- GlowEffect: a soft coloured light behind an element ---------- */
export type GlowEffectProps = {
  className?: string;
  style?: CSSProperties;
  colors: string[];
  mode?: "rotate" | "breathe" | "static";
  blur?: number;
  duration?: number;
  scale?: number;
};

export function GlowEffect({ className, style, colors, mode = "rotate", blur = 16, duration = 5, scale = 1 }: GlowEffectProps) {
  const reduce = useReducedMotion();
  const still = reduce || mode === "static";
  const base = { repeat: Infinity, duration, ease: "linear" } as const;
  // rotate: the conic's start angle is a CSS variable that motion writes every frame (CSS variables in the
  // gradient stay tokens; interpolating two whole gradient strings with var() in them is not reliable)
  const conic = `conic-gradient(from var(--glow-angle, 0deg) at 50% 50%, ${colors.join(", ")})`;
  const animate: TargetAndTransition | undefined = still
    ? undefined
    : mode === "rotate"
      ? { "--glow-angle": ["0deg", "360deg"], transition: base }
      : { scale: [scale, 1.05 * scale, scale], opacity: [0.7, 1, 0.7], transition: { ...base, repeatType: "mirror" as const } };
  return (
    <motion.span
      aria-hidden="true"
      className={cn("pointer-events-none absolute inset-0 block h-full w-full rounded-[inherit]", className)}
      style={{ ...style, background: conic, filter: `blur(${blur}px)`, scale }}
      animate={animate}
    />
  );
}

/* ---------- Magnetic: the child leans toward the pointer ---------- */
const SPRING = { stiffness: 26.7, damping: 4.1, mass: 0.2 };
export type MagneticProps = { children: ReactNode; intensity?: number; range?: number; springOptions?: SpringOptions; className?: string };

export function Magnetic({ children, intensity = 0.6, range = 100, springOptions = SPRING, className }: MagneticProps) {
  const reduce = useReducedMotion();
  const [hovered, setHovered] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, springOptions);
  const sy = useSpring(y, springOptions);

  useEffect(() => {
    if (reduce || !hovered) return;
    const move = (e: PointerEvent) => {
      if (e.pointerType !== "mouse" || !ref.current) return;
      const r = ref.current.getBoundingClientRect();
      const dx = e.clientX - (r.left + r.width / 2);
      const dy = e.clientY - (r.top + r.height / 2);
      const dist = Math.hypot(dx, dy);
      const k = dist <= range ? 1 - dist / range : 0;
      x.set(dx * intensity * k);
      y.set(dy * intensity * k);
    };
    document.addEventListener("pointermove", move);
    return () => document.removeEventListener("pointermove", move);
  }, [reduce, hovered, intensity, range, x, y]);

  return (
    <motion.span
      ref={ref}
      className={cn("inline-flex", className)}
      onPointerEnter={(e) => e.pointerType === "mouse" && setHovered(true)}
      onPointerLeave={() => {
        setHovered(false);
        x.set(0);
        y.set(0);
      }}
      style={reduce ? undefined : { x: sx, y: sy }}
    >
      {children}
    </motion.span>
  );
}

/* ---------- AnimatedNumber: a number that springs to its new value ---------- */
export type AnimatedNumberProps = { value: number; className?: string; springOptions?: SpringOptions; locale?: string };

export function AnimatedNumber({ value, className, springOptions = { bounce: 0, duration: 900 }, locale = "en-IN" }: AnimatedNumberProps) {
  const reduce = useReducedMotion();
  const spring = useSpring(reduce ? value : 0, springOptions);
  const display = useTransform(spring, (n) => Math.round(n).toLocaleString(locale));
  useEffect(() => {
    if (reduce) spring.jump(value);
    else spring.set(value);
  }, [spring, value, reduce]);
  return <motion.span className={cn("tabular-nums", className)}>{display}</motion.span>;
}
