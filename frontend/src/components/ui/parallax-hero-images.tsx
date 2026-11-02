"use client";
import { useEffect, useMemo, memo } from "react";
import {
  motion,
  useMotionValue,
  useReducedMotion,
  useSpring,
  useTransform,
  MotionValue,
} from "motion/react";
import { cn } from "@/lib/utils";

type ImagePosition = {
  src: string;
  position:
    | "top-left"
    | "top-right"
    | "mid-left"
    | "mid-right"
    | "bottom-left"
    | "bottom-right"
    | "far-left"
    | "far-right";
  depth: number;
  delay: number;
};

const positionStyles: Record<
  ImagePosition["position"],
  { top: string; left?: string; right?: string }
> = {
  "top-left": { top: "8%", left: "4%" },
  "top-right": { top: "8%", right: "4%" },
  "mid-left": { top: "38%", left: "6%" },
  "mid-right": { top: "38%", right: "6%" },
  "bottom-left": { top: "68%", left: "4%" },
  "bottom-right": { top: "68%", right: "4%" },
  "far-left": { top: "52%", left: "2%" },
  "far-right": { top: "52%", right: "2%" },
};

const positionOrder: ImagePosition["position"][] = [
  "top-left",
  "top-right",
  "mid-left",
  "mid-right",
  "bottom-left",
  "bottom-right",
  "far-left",
  "far-right",
];

type DepthVariant = "default" | "edge-focus";

const depthValuesByVariant: Record<DepthVariant, number[]> = {
  default: [0.3, 0.35, 0.9, 0.85, 0.4, 0.45, 0.25, 0.2],
  "edge-focus": [0.85, 0.9, 0.3, 0.35, 0.8, 0.85, 0.4, 0.45],
};

const SPRING_CONFIG = { damping: 25, stiffness: 120 };

/*
 * Aceternity "ParallaxHeroImages" (registry @aceternity/parallax-hero-images-demo): mouse-position motion values,
 * springs and depth layers are unchanged. Bima Sarthi changes (also in DESIGN.md): `alts` gives each image real alt
 * text (the original was alt=""); pointer parallax is disabled on touch / coarse pointers and under reduced motion
 * (the layers then simply sit still); under reduced motion the blur-in entrance is skipped; `positions` lets the caller
 * choose which of the eight slots to use (the original filled them in order).
 */
export interface ParallaxHeroImagesProps {
  images: string[];
  className?: string;
  imageClassName?: string;
  variant?: DepthVariant;
  alts?: string[];
  positions?: ImagePosition["position"][];
}

export const ParallaxHeroImages = ({
  images,
  className,
  imageClassName,
  variant = "default",
  alts,
  positions: slots,
}: ParallaxHeroImagesProps) => {
  const reduce = !!useReducedMotion();
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  const smoothMouseX = useSpring(mouseX, SPRING_CONFIG);
  const smoothMouseY = useSpring(mouseY, SPRING_CONFIG);

  const positions = useMemo(() => {
    const limitedImages = images.slice(0, 8);
    const depthValues = depthValuesByVariant[variant];
    return limitedImages.map((src, index) => {
      const position = slots?.[index] ?? positionOrder[index];
      return {
        src,
        alt: alts?.[index] ?? "",
        position,
        depth: depthValues[positionOrder.indexOf(position)],
        delay: index * 0.12,
      };
    });
  }, [images, variant, alts, slots]);

  useEffect(() => {
    // no pointer parallax on touch / coarse pointers, or when the visitor asked for less motion
    const coarse = typeof window.matchMedia === "function" && window.matchMedia("(hover: none), (pointer: coarse)").matches;
    if (reduce || coarse) return;
    const handleMouseMove = (e: MouseEvent) => {
      const x = (e.clientX / window.innerWidth) * 2 - 1;
      const y = (e.clientY / window.innerHeight) * 2 - 1;
      mouseX.set(x);
      mouseY.set(y);
    };

    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, [mouseX, mouseY, reduce]);

  return (
    <div
      className={cn(
        "pointer-events-none absolute inset-0 overflow-hidden",
        className,
      )}
    >
      {positions.map((pos, index) => (
        <ParallaxImage
          key={`${pos.src}-${index}`}
          src={pos.src}
          alt={pos.alt}
          reduce={reduce}
          position={pos.position}
          depth={pos.depth}
          delay={pos.delay}
          imageClassName={imageClassName}
          smoothMouseX={smoothMouseX}
          smoothMouseY={smoothMouseY}
        />
      ))}
    </div>
  );
};

interface ParallaxImageProps extends ImagePosition {
  alt: string;
  reduce: boolean;
  imageClassName?: string;
  smoothMouseX: MotionValue<number>;
  smoothMouseY: MotionValue<number>;
}

const ParallaxImage = memo(function ParallaxImage({
  src,
  alt,
  reduce,
  position,
  depth,
  delay,
  imageClassName,
  smoothMouseX,
  smoothMouseY,
}: ParallaxImageProps) {
  const maxOffset = 40;

  const translateX = useTransform(
    smoothMouseX,
    [-1, 1],
    [-maxOffset * depth, maxOffset * depth],
  );

  const translateY = useTransform(
    smoothMouseY,
    [-1, 1],
    [-maxOffset * depth, maxOffset * depth],
  );

  const posStyle = positionStyles[position];

  return (
    <motion.div
      className="absolute"
      style={{
        top: posStyle.top,
        left: posStyle.left,
        right: posStyle.right,
        x: translateX,
        y: translateY,
        zIndex: Math.round(depth * 10),
      }}
      initial={reduce ? false : { opacity: 0, filter: "blur(20px)", scale: 0.9 }}
      animate={{ opacity: 1, filter: "blur(0px)", scale: 1 }}
      transition={{
        duration: 0.8,
        delay: delay,
        ease: [0.25, 0.1, 0.25, 1],
      }}
    >
      <img
        src={src}
        alt={alt}
        loading="lazy"
        decoding="async"
        className={cn(
          "aspect-4/3 h-20 w-32 rounded-card object-cover shadow-lift ring-1 ring-ink/10 sm:h-40 sm:w-56 md:h-52 md:w-80",
          imageClassName,
        )}
      />
    </motion.div>
  );
});
