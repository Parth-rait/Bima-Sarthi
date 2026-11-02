import { Suspense, lazy, type CSSProperties } from "react";
import { Boundary } from "@/components/ds/Boundary";
import { Button } from "@/components/ds/Button";
import { SKY, SKY_STATIC } from "@/design/atmosphere";
import { cn } from "@/lib/utils";
import { useSession } from "@/state/store";

const CloudShader = lazy(() => import("@/components/ui/cloud-shader").then((m) => ({ default: m.CloudShader })));

function rgba(hex: string, a: number) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}

/** The static sunset: pure CSS, built from the same palette as the shader (src/design/atmosphere.ts). */
export function staticSkyStyle(): CSSProperties {
  const [sx, sy] = SKY_STATIC.sunAt.split(" ");
  const layers = [
    `radial-gradient(ellipse 34% 26% at ${sx} ${sy}, ${SKY_STATIC.sun}, transparent 72%)`,
    ...SKY_STATIC.clouds.map(([x, y, w, h]) => `radial-gradient(ellipse ${w / 2}% ${h / 2}% at ${x}% ${y}%, ${rgba(SKY.cloudColor, SKY_STATIC.cloudAlpha)}, transparent 72%)`),
    `linear-gradient(180deg, transparent ${SKY_STATIC.lavenderAtPct - 18}%, ${SKY_STATIC.lavenderBand} ${SKY_STATIC.lavenderAtPct}%, transparent ${SKY_STATIC.lavenderAtPct + 18}%)`,
    `linear-gradient(180deg, ${SKY.skyTopColor} 0%, ${SKY.skyBottomColor} 100%)`,
  ];
  return { backgroundImage: layers.join(", "), backgroundColor: SKY.skyBottomColor };
}

/**
 * The sky behind a hero. Always paints the static CSS sunset first (so nothing flashes and the fallback is already there),
 * then, when `shader` is true, the Aceternity CloudShader (lazy chunk) is laid over it. If WebGL fails the shader calls
 * `onUnavailable` and the static sky simply stays. Decorative: aria-hidden, never takes pointer events.
 */
export function SkyBackdrop({ shader, onUnavailable, className }: { shader: boolean; onUnavailable?: () => void; className?: string }) {
  return (
    <div aria-hidden="true" data-sky={shader ? "shader" : "static"} className={cn("pointer-events-none absolute inset-0 -z-10 overflow-hidden", className)} style={staticSkyStyle()}>
      {shader ? (
        <Boundary fallback={null}>
          <Suspense fallback={null}>
            <CloudShader
              className="absolute inset-0 h-full min-h-0"
              cloudColor={SKY.cloudColor}
              skyTopColor={SKY.skyTopColor}
              skyBottomColor={SKY.skyBottomColor}
              speed={SKY.speed}
              count={SKY.count}
              renderScale={SKY.renderScale}
              maxFps={SKY.maxFps}
              maxDpr={SKY.maxDpr}
              onUnavailable={onUnavailable}
            />
          </Suspense>
        </Boundary>
      ) : null}
    </div>
  );
}

/** The "Animate the sky" switch: a real toggle button (aria-pressed), 44px, with a one-line explanation. */
export function SkyToggle({ pressed, onToggle, className }: { pressed: boolean; onToggle: () => void; className?: string }) {
  const { t } = useSession();
  return (
    <Button variant="secondary" size="sm" aria-pressed={pressed} onClick={onToggle} title={t("sky_animate_h")} className={cn("bg-ivory/80", className)}>
      <span aria-hidden="true" className={cn("inline-block size-2.5 rounded-full border border-ink", pressed && "bg-ink")} />
      {t("sky_animate")}
    </Button>
  );
}
