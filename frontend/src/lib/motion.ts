import type { CSSProperties } from "react";
import { useReducedMotion } from "motion/react";

/*
 * The motion language for the operate surface, in one place so a screen cannot invent its own curve.
 * Mirrors the CSS: --dur-3 is 380ms and --ease-out is the same decelerating curve, so a step that reveals
 * itself in CSS and a step that is swapped by React feel like the same gesture.
 * Anything that must be instant for a user who asked for reduced motion returns an empty prop bag: the
 * component renders with no initial state at all, rather than animating and then being over-ridden.
 */
export const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];
export const DUR = { press: 0.14, row: 0.24, screen: 0.38 } as const;

export type EnterProps = { initial?: { opacity: number; y: number }; animate?: { opacity: number; y: number }; transition?: { duration: number; ease: [number, number, number, number] } };

/** A block arriving: 18px up into place, nothing leaving. Exit animations are deliberately not used — they keep the
 * previous screen in the DOM while it fades, which is exactly wrong for a gated flow where the old step must be gone. */
export function useArrive(distance = 18): EnterProps {
  return useReducedMotion() ? {} : { initial: { opacity: 0, y: distance }, animate: { opacity: 1, y: 0 }, transition: { duration: DUR.screen, ease: EASE } };
}

/**
 * Stagger index for a row that settles into the sheet (operate.css reads it as `--i`).
 * A number on the element rather than nth-child rules because the lists are long, and a row's position is not
 * the same thing as its order in the DOM once facts are grouped.
 */
export function rowOrder(i: number): CSSProperties {
  return { ["--i" as string]: String(Math.min(i, 8)) } as CSSProperties;
}
