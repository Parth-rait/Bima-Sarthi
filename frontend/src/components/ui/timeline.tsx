"use client";
import {
  useReducedMotion,
  useScroll,
  useTransform,
  motion,
} from "motion/react";
import React, { useEffect, useRef, useState } from "react";
import { TIMELINE } from "@/design/atmosphere";

/*
 * Aceternity "Timeline" (registry @aceternity/timeline-demo): scroll progress is unchanged (useScroll on the
 * container, offset ["start 10%", "end 50%"], the line grows from 0 to the measured height).
 * Bima Sarthi changes (also in DESIGN.md): the unused useMotionValueEvent import is dropped; the hard-coded "Changelog from my journey" heading is replaced by optional
 * `heading` / `description` props (omitted = no header); the white/neutral/dark: classes and the purple-blue line use
 * our tokens (colours in src/design/atmosphere.ts); the line's height is re-measured with a ResizeObserver (the original
 * measured once, so images loading later left it short); with reduced motion the line is drawn full, not scroll-driven;
 * titles are display-serif and a little smaller; an entry may carry `id` (anchor target) and `number` (the step number, shown as a numeral above the title).
 */
interface TimelineEntry {
  title: string;
  content: React.ReactNode;
  id?: string;
  number?: number;
}

export const Timeline = ({
  data,
  heading,
  description,
  headingId,
}: {
  data: TimelineEntry[];
  heading?: string;
  description?: string;
  headingId?: string;
}) => {
  const ref = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(0);
  const reduce = useReducedMotion();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setHeight(el.getBoundingClientRect().height);
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start 10%", "end 50%"],
  });

  const heightTransform = useTransform(scrollYProgress, [0, 1], [0, height]);
  const opacityTransform = useTransform(scrollYProgress, [0, 0.1], [0, 1]);

  return (
    <div className="w-full font-sans" ref={containerRef}>
      {heading ? (
        <div className="mx-auto max-w-[90rem] py-10 md:py-14">
          <h2 id={headingId} className="m-0 max-w-4xl font-display text-h2 font-medium text-ink">
            {heading}
          </h2>
          {description ? <p className="mt-3 max-w-[68ch] text-lead text-ink">{description}</p> : null}
        </div>
      ) : null}

      <div ref={ref} className="relative mx-auto max-w-[90rem] pb-20">
        {data.map((item, index) => (
          <div
            key={index}
            id={item.id}
            className="flex justify-start pt-10 md:gap-10 md:pt-28"
          >
            <div className="sticky top-32 z-40 flex flex-col items-center self-start md:w-full md:max-w-xs md:flex-row lg:max-w-sm">
              <div className="absolute left-3 flex h-10 w-10 items-center justify-center rounded-full bg-ivory md:left-3">
                <div className="h-4 w-4 rounded-full border border-line-strong bg-peach p-2" />
              </div>
              <div className="hidden md:block md:pl-20">
                {item.number ? <span aria-hidden="true" className="mb-1 block font-display text-[2.5rem] leading-none text-ink-soft">{item.number}</span> : null}
                <h3 className="m-0 font-display text-h2 font-medium text-ink">
                  {item.number ? <span className="sr-only">Step {item.number}: </span> : null}
                  {item.title}
                </h3>
              </div>
            </div>

            <div className="relative w-full pl-20 pr-4 md:pl-4">
              <div className="md:hidden">
                {item.number ? <span aria-hidden="true" className="mb-1 block font-display text-[2rem] leading-none text-ink-soft">{item.number}</span> : null}
                <h3 className="mb-4 mt-0 text-left font-display text-h3 font-medium text-ink">
                  {item.number ? <span className="sr-only">Step {item.number}: </span> : null}
                  {item.title}
                </h3>
              </div>
              {item.content}
            </div>
          </div>
        ))}
        <div
          aria-hidden="true"
          style={{
            height: height + "px",
          }}
          className="absolute left-8 top-0 w-[2px] overflow-hidden bg-line [mask-image:linear-gradient(to_bottom,transparent_0%,black_10%,black_90%,transparent_100%)]"
        >
          <motion.div
            style={{
              height: reduce ? height : heightTransform,
              opacity: reduce ? 1 : opacityTransform,
              backgroundImage: `linear-gradient(to top, ${TIMELINE.progressFrom} 0%, ${TIMELINE.progressVia} 10%, transparent 100%)`,
            }}
            className="absolute inset-x-0 top-0 w-[2px] rounded-full"
          />
        </div>
      </div>
    </div>
  );
};
