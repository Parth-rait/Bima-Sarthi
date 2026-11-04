import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/*
 * tailwind-merge decides whether `text-foo` is a font-size or a text colour from its own validators, and it does not
 * know this project's @theme scale. Without this it reads `text-h1` as a colour and silently drops the real colour
 * that follows it (or the size, if the colour came first) — so `cn("text-h1 text-ink")` rendered headings at body size.
 * Registering the scale here keeps size and colour as separate groups. Add new --text-* tokens to this list.
 */
const TYPE_SCALE = ["display", "h1", "h2", "h3", "lead", "body", "meta", "control"] as const;

const twMerge = extendTailwindMerge({
  extend: { classGroups: { "font-size": [{ text: [...TYPE_SCALE] }] } },
});

/** Merge class names, letting later Tailwind utilities win (shadcn convention). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
