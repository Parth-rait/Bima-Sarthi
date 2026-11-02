import { useSyncExternalStore } from "react";

/** Subscribe to a CSS media query. `server` is what to report where matchMedia does not exist (tests, SSR). */
export function useMediaQuery(query: string, server = false): boolean {
  return useSyncExternalStore(
    (cb) => {
      if (typeof window === "undefined" || typeof window.matchMedia !== "function") return () => {};
      const mq = window.matchMedia(query);
      mq.addEventListener?.("change", cb);
      return () => mq.removeEventListener?.("change", cb);
    },
    () => (typeof window !== "undefined" && typeof window.matchMedia === "function" ? window.matchMedia(query).matches : server),
    () => server,
  );
}

/** True when the visitor asked for less motion. Every animation in the app is gated on this. */
export function usePrefersReducedMotion(): boolean {
  return useMediaQuery("(prefers-reduced-motion: reduce)");
}
