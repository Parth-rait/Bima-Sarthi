import { Suspense, lazy } from "react";
import { Boundary } from "@/components/ds/Boundary";
import { usePrefersReducedMotion } from "@/hooks/useMedia";
import { cn } from "@/lib/utils";

const Chromatic = lazy(() => import("@/components/ui/chromatic-image").then((m) => ({ default: m.ChromaticImage })));

/** True only where a WebGL context can really exist (not jsdom, not a browser with WebGL off). Checked lazily, once. */
let webgl: boolean | undefined;
export function hasWebGL(): boolean {
  if (webgl !== undefined) return webgl;
  if (typeof window === "undefined" || typeof (window as unknown as { WebGLRenderingContext?: unknown }).WebGLRenderingContext === "undefined") return (webgl = false);
  try {
    const c = document.createElement("canvas");
    webgl = !!(c.getContext("webgl") || c.getContext("experimental-webgl"));
  } catch {
    webgl = false;
  }
  return webgl;
}

/**
 * The dossier artwork. With WebGL and normal motion it is the Aceternity ChromaticImage (pointer-responsive displacement,
 * chromatic shift, tilt), loaded as a separate chunk. Otherwise, and while that chunk loads or if it fails, it is the same
 * artwork as a plain <img> (also whenever `plain` is set, e.g. on low-power devices). The alt text is on the image in every case.
 */
export function ArtworkImage({ src, alt, className, background = "#f2d5c2", width, height, plain: forcePlain = false }: { src: string; alt: string; className?: string; background?: string; width?: number; height?: number; plain?: boolean }) {
  const reduce = usePrefersReducedMotion();
  const plain = <img src={src} alt={alt} width={width} height={height} className="size-full object-cover" />;
  if (reduce || forcePlain || !hasWebGL()) return <div className={cn("relative overflow-hidden", className)}>{plain}</div>;
  return (
    <Boundary fallback={<div className={cn("relative overflow-hidden", className)}>{plain}</div>}>
      <Suspense fallback={<div className={cn("relative overflow-hidden", className)}>{plain}</div>}>
        <Chromatic src={src} alt={alt} className={className} backgroundColor={background} zoom={0.12} displacement={0.035} chromaticShift={0.008} tilt={0.25} />
      </Suspense>
    </Boundary>
  );
}
