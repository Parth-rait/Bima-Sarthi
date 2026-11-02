"use client";
import React from "react";
import { motion, useReducedMotion } from "motion/react";
import { LAMP } from "@/design/atmosphere";
import { cn } from "@/lib/utils";

/*
 * Aceternity "Lamp" (registry @aceternity/lamp-demo), geometry and technique unchanged: two conic-gradient light
 * beams, a wide blurred glow, a small bright core, a thin lamp line, and masks that fade the beams into the page.
 * Bima Sarthi changes (also listed in DESIGN.md): cyan -> sunlight colours read from src/design/atmosphere.ts (LAMP);
 * the conic gradients are written out explicitly (the original relied on Tailwind v3's bg-gradient-conic, which does
 * not exist in Tailwind v4); the demo heading (gradient text, "Build lamps...") is removed (LampDemo is not exported);
 * reduced motion shows the final beam widths without animating; the decorative layers are aria-hidden.
 */
export const LampContainer = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => {
  const reduce = useReducedMotion();
  const grow = (from: string, to: string, fade = false) =>
    reduce
      ? {}
      : {
          initial: fade ? { opacity: 0.5, width: from } : { width: from },
          whileInView: fade ? { opacity: 1, width: to } : { width: to },
          transition: { delay: 0.3, duration: 0.8, ease: "easeInOut" as const },
        };
  const bg = "bg-[var(--lamp-bg)]";
  return (
    <div
      style={
        {
          "--lamp-bg": LAMP.background,
          "--lamp-beam": LAMP.beam,
          "--lamp-glow": LAMP.glow,
          "--lamp-core": LAMP.core,
          "--lamp-line": LAMP.line,
        } as React.CSSProperties
      }
      className={cn(
        "relative flex min-h-screen w-full z-0 flex-col items-center justify-center overflow-hidden rounded-md",
        bg,
        className
      )}
    >
      <div
        aria-hidden="true"
        className="relative flex w-full flex-1 scale-y-125 items-center justify-center isolate z-0 "
      >
        <motion.div
          {...grow("15rem", "30rem", true)}
          style={{
            backgroundImage: `conic-gradient(from 70deg at center top, ${LAMP.beam}, transparent, transparent)`,
          }}
          className="absolute inset-auto right-1/2 h-56 overflow-visible w-[30rem]"
        >
          <div className={cn("absolute w-[100%] left-0 h-40 bottom-0 z-20 [mask-image:linear-gradient(to_top,white,transparent)]", bg)} />
          <div className={cn("absolute w-40 h-[100%] left-0 bottom-0 z-20 [mask-image:linear-gradient(to_right,white,transparent)]", bg)} />
        </motion.div>
        <motion.div
          {...grow("15rem", "30rem", true)}
          style={{
            backgroundImage: `conic-gradient(from 290deg at center top, transparent, transparent, ${LAMP.beam})`,
          }}
          className="absolute inset-auto left-1/2 h-56 w-[30rem]"
        >
          <div className={cn("absolute w-40 h-[100%] right-0 bottom-0 z-20 [mask-image:linear-gradient(to_left,white,transparent)]", bg)} />
          <div className={cn("absolute w-[100%] right-0 h-40 bottom-0 z-20 [mask-image:linear-gradient(to_top,white,transparent)]", bg)} />
        </motion.div>
        <div className={cn("absolute top-1/2 h-48 w-full translate-y-12 scale-x-150 blur-2xl", bg)}></div>
        <div className="absolute top-1/2 z-50 h-48 w-full bg-transparent opacity-10 backdrop-blur-md"></div>
        <div
          style={{ opacity: LAMP.glowOpacity }}
          className="absolute inset-auto z-50 h-36 w-[28rem] -translate-y-1/2 rounded-full bg-[var(--lamp-glow)] blur-3xl"
        ></div>
        <motion.div
          {...grow("8rem", "16rem")}
          className="absolute inset-auto z-30 h-36 w-64 -translate-y-[6rem] rounded-full bg-[var(--lamp-core)] blur-2xl"
        ></motion.div>
        <motion.div
          {...grow("15rem", "30rem")}
          className="absolute inset-auto z-50 h-0.5 w-[30rem] -translate-y-[7rem] bg-[var(--lamp-line)] "
        ></motion.div>

        <div className={cn("absolute inset-auto z-40 h-44 w-full -translate-y-[12.5rem]", bg)}></div>
      </div>

      <div className="relative z-50 flex -translate-y-80 flex-col items-center px-5">
        {children}
      </div>
    </div>
  );
};
