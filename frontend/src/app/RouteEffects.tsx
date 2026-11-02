import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigationType } from "react-router";
import type { Key } from "@/i18n";
import { useSession } from "@/state/store";

const TITLES: Array<[RegExp, Key]> = [
  [/^\/$/, "title_home"],
  [/^\/about$/, "title_about"],
  [/^\/how-it-works$/, "title_how"],
  [/^\/check-claim$/, "title_check"],
  [/^\/action-plan$/, "title_plan"],
  [/^\/cases$/, "title_cases"],
  [/^\/privacy$/, "title_privacy"],
  [/^\/help$/, "title_help"],
  [/^\/results\/[^/]+$/, "title_results"],
  [/^\/dev\/components$/, "title_dev"],
];
export const titleKeyFor = (pathname: string): Key => TITLES.find(([re]) => re.test(pathname))?.[1] ?? "title_404";

/** Scroll positions by history entry, so Back returns to where the reader was. In memory only. */
const positions = new Map<string, number>();

/**
 * What a route change must do, in one place:
 *  - set document.title per page (and announce it to screen readers through a polite live region);
 *  - restore scroll on Back/Forward, scroll to a #hash target, else go to the top;
 *  - move keyboard focus to the new page's <h1> (not on the very first load, and not when only the #hash changed).
 */
export function RouteEffects() {
  const loc = useLocation();
  const nav = useNavigationType();
  const { t } = useSession();
  const first = useRef(true);
  const lastPath = useRef(loc.pathname);
  const [announcement, setAnnouncement] = useState("");

  const title = t(titleKeyFor(loc.pathname));
  useEffect(() => {
    document.title = loc.pathname === "/" ? `Bima Sarthi: ${title}` : `${title} | Bima Sarthi`;
    setAnnouncement(title);
  }, [title, loc.pathname]);

  // remember where we were when leaving this history entry
  useEffect(() => {
    const key = loc.key;
    return () => {
      positions.set(key, window.scrollY);
    };
  }, [loc.key]);

  useEffect(() => {
    const samePage = lastPath.current === loc.pathname;
    lastPath.current = loc.pathname;
    const id = loc.hash ? decodeURIComponent(loc.hash.slice(1)) : "";
    const target = id ? document.getElementById(id) : null;
    const wasFirst = first.current;
    first.current = false;
    let stop: (() => void) | undefined;
    if (target) {
      target.scrollIntoView?.();
      if (!wasFirst) target.focus?.({ preventScroll: true });
    } else if (id) {
      // the page is a lazy chunk and may not have rendered yet: wait (up to 5 s) for the anchor to appear, then go to it
      window.scrollTo?.(0, 0);
      const main = document.getElementById("main");
      if (main && typeof MutationObserver !== "undefined") {
        const mo = new MutationObserver(() => {
          const el = document.getElementById(id);
          if (!el) return;
          mo.disconnect();
          el.scrollIntoView?.();
          el.focus?.({ preventScroll: true });
        });
        mo.observe(main, { childList: true, subtree: true });
        const timer = setTimeout(() => mo.disconnect(), 5000);
        stop = () => {
          mo.disconnect();
          clearTimeout(timer);
        };
      }
    } else if (nav === "POP" && positions.has(loc.key)) {
      window.scrollTo?.(0, positions.get(loc.key) ?? 0);
    } else if (!samePage || !wasFirst) {
      window.scrollTo?.(0, 0);
    }
    if (!wasFirst && !samePage && !id) {
      const h = document.querySelector<HTMLElement>("main [data-page-heading]") ?? document.getElementById("main");
      h?.focus({ preventScroll: true });
    }
    return stop;
  }, [loc.pathname, loc.hash, loc.key, nav]);

  return (
    <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
      {announcement}
    </div>
  );
}
