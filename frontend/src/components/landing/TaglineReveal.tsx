import { useEffect, useRef, useState } from "react";
import { usePrefersReducedMotion } from "@/hooks/useMedia";

/**
 * The mandatory tagline moment: one large statement, separate from the hero.
 * Each word moves from muted to full ink in reading order, once, when the line enters view.
 * Reduced motion shows the final text immediately.
 */
export function TaglineReveal({ id, text, className }: { id: string; text: string; className?: string }) {
  const reduced = usePrefersReducedMotion();
  const [active, setActive] = useState(reduced);
  const ref = useRef<HTMLHeadingElement>(null);
  const words = text.split(" ");

  useEffect(() => {
    if (reduced || typeof IntersectionObserver === "undefined") {
      setActive(true);
      return;
    }
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setActive(true);
          io.disconnect();
        }
      },
      { threshold: 0.4 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [reduced]);

  return (
    <h2 ref={ref} id={id} className={`m-0 max-w-[680px] font-display text-3xl font-semibold text-ink sm:text-4xl lg:text-5xl ${className ?? ""}`}>
      {words.map((word, i) => (
        <span
          key={`${word}-${i}`}
          style={{
            opacity: active ? 1 : 0.3,
            transition: reduced ? undefined : `opacity 700ms cubic-bezier(0.22, 1, 0.36, 1) ${i * 60}ms`,
          }}
        >
          {word}
          {i < words.length - 1 ? " " : ""}
        </span>
      ))}
    </h2>
  );
}
