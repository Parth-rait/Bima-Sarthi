import { useEffect, useState } from "react";
import markUrl from "@/assets/art/mark.svg";
import { useSession } from "@/state/store";
import { usePrefersReducedMotion } from "@/hooks/useMedia";
import { useAppReady } from "./ServiceStatus";

/** Show nothing unless initialisation is slow enough to notice (150 ms): a splash that flashes is worse than none. */
const SHOW_AFTER_MS = 150;

/**
 * Entry overlay. It exists only while the app is really initialising (fonts + health check, see ServiceProvider);
 * the moment that work settles it is removed, with a short fade that reduced-motion visitors do not get. There is no timer
 * that holds it open and no fake progress: it states what is happening and nothing else.
 */
export function Splash() {
  const ready = useAppReady();
  const { t } = useSession();
  const reduce = usePrefersReducedMotion();
  const [show, setShow] = useState(false);
  const [leaving, setLeaving] = useState(false);

  // not ready for 150 ms: it is slow enough to deserve a status
  useEffect(() => {
    if (ready) return;
    const id = setTimeout(() => setShow(true), SHOW_AFTER_MS);
    return () => clearTimeout(id);
  }, [ready]);
  // ready: fade out, then remove. The fade is the only time it outlives the work (220 ms, none under reduced motion)
  useEffect(() => {
    if (!ready || !show) return;
    setLeaving(true);
    const id = setTimeout(() => {
      setShow(false);
      setLeaving(false);
    }, reduce ? 0 : 220);
    return () => clearTimeout(id);
  }, [ready, show, reduce]);

  if (!show) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed inset-0 z-[100] grid place-items-center bg-ivory text-ink transition-opacity duration-200 motion-reduce:transition-none ${leaving ? "opacity-0" : "opacity-100"}`}
    >
      <div className="flex flex-col items-center gap-4">
        <img src={markUrl} alt="" width={56} height={56} />
        <p className="m-0 font-display text-[1.75rem] font-medium">Bima Sarthi</p>
        <p className="m-0 text-ink-soft">{t("splash_text")}</p>
      </div>
    </div>
  );
}
