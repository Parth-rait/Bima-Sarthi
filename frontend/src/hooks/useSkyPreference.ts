import { useCallback, useState } from "react";
import { hasWebGL } from "@/components/landing/ArtworkImage";
import { usePrefersReducedMotion } from "@/hooks/useMedia";

/*
 * The "Animate the sky" preference. The ONLY thing this app stores in the browser (localStorage, one key, "on" | "off";
 * no personal data). Every access is wrapped in try/catch: private windows, blocked storage and tests must still work.
 * The Privacy page says so; src/test/static.test.ts allows localStorage in this one file only.
 */
const KEY = "bimasarthi.sky";
export type SkyPref = "on" | "off" | null;

function read(): SkyPref {
  try {
    const v = window.localStorage.getItem(KEY);
    return v === "on" || v === "off" ? v : null;
  } catch {
    return null;
  }
}
function write(v: "on" | "off") {
  try {
    window.localStorage.setItem(KEY, v);
  } catch {
    /* storage unavailable: the choice lasts until the page is closed */
  }
}

/** Low-power heuristic: 4 or fewer logical cores, or 4 GB or less of memory (where the browser reports it). */
export function isLowPower(): boolean {
  if (typeof navigator === "undefined") return false;
  const n = navigator as Navigator & { deviceMemory?: number };
  return (typeof n.hardwareConcurrency === "number" && n.hardwareConcurrency > 0 && n.hardwareConcurrency <= 4) || (typeof n.deviceMemory === "number" && n.deviceMemory <= 4);
}

export interface SkyState {
  /** WebGL context available at all */
  webgl: boolean;
  /** true = mount the CloudShader (it draws one still frame under reduced motion); false = the static CSS sky */
  useShader: boolean;
  /** true = the clouds should move (shader mounted AND motion allowed) */
  animating: boolean;
  /** show the "Animate the sky" toggle (needs WebGL; hidden under reduced motion) */
  canToggle: boolean;
  lowPower: boolean;
  reduced: boolean;
  toggle: () => void;
  /** the shader reported failure (no WebGL context, compile error, context lost): drop to the static sky */
  markUnavailable: () => void;
}

export function useSkyAnimation(): SkyState {
  const reduced = usePrefersReducedMotion();
  const [pref, setPref] = useState<SkyPref>(read);
  const [failed, setFailed] = useState(false);
  const webgl = hasWebGL();
  const lowPower = isLowPower();
  const on = pref === "on" ? true : pref === "off" ? false : !lowPower;
  const useShader = webgl && !failed && on;
  const toggle = useCallback(() => {
    const next = on ? "off" : "on";
    write(next);
    setPref(next);
  }, [on]);
  const markUnavailable = useCallback(() => setFailed(true), []);
  return { webgl, useShader, animating: useShader && !reduced, canToggle: webgl && !failed && !reduced, lowPower, reduced, toggle, markUnavailable };
}
