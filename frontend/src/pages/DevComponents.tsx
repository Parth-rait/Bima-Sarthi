import { Suspense, lazy, useRef, useState } from "react";
import { Boundary } from "@/components/ds/Boundary";
import { Loader } from "@/components/ds/Loader";
import { Band, Wrap } from "@/components/ds/Section";
import { Tag } from "@/components/ds/StatusBadge";
import { ArtworkImage, hasWebGL } from "@/components/landing/ArtworkImage";
import { SkyBackdrop, SkyToggle } from "@/components/landing/SkyBackdrop";
import { ART } from "@/content/art";
import { SCENARIOS } from "@/content/scenarios";
import { STAGES } from "@/content/stages";
import { WorkStage, type StageStep } from "@/components/stage/WorkStage";
import { PlanSection } from "@/components/Plan";
import { DeadlineTimeline } from "@/components/charts/DeadlineTimeline";
import { FindingsChart } from "@/components/charts/FindingsChart";
import { Spark } from "@/components/ds/Spark";
import type { Finding, Plan, PlanItem } from "@/api";
import { Tumble } from "@/components/flow/Tumble";
import { motion, useReducedMotion } from "motion/react";
import { usePrefersReducedMotion } from "@/hooks/useMedia";
import { isLowPower, useSkyAnimation } from "@/hooks/useSkyPreference";

const GlassChip = lazy(() => import("@/components/landing/GlassChip"));
const LiquidGlass = lazy(() => import("@/components/ui/liquid-glass").then((m) => ({ default: m.LiquidGlass })));
const Carousel = lazy(() => import("@/components/ui/carousel"));
const DraggableScenarios = lazy(() => import("@/components/landing/DraggableScenarios"));
const ParallaxHeroImages = lazy(() => import("@/components/ui/parallax-hero-images").then((m) => ({ default: m.ParallaxHeroImages })));
const FileUpload = lazy(() => import("@/components/ui/file-upload").then((m) => ({ default: m.FileUpload })));
const LampContainer = lazy(() => import("@/components/ui/lamp").then((m) => ({ default: m.LampContainer })));
const Timeline = lazy(() => import("@/components/ui/timeline").then((m) => ({ default: m.Timeline })));

function Panel({ id, title, children, check, tone = "ivory" }: { id: string; title: string; children: React.ReactNode; check: string[]; tone?: "ivory" | "peach" }) {
  return (
    <Band tone={tone} pad="tight" labelledBy={id}>
      <Wrap width="wide">
        <h2 id={id} className="m-0 font-display text-h2 font-medium text-ink">
          {title}
        </h2>
        <div className="mt-6">{children}</div>
        <div className="mt-6 max-w-[70ch] border-t border-gold pt-3">
          <p className="m-0 font-semibold text-ink">What to check in the browser</p>
          <ul className="mb-0 mt-2 list-disc pl-5 text-control">
            {check.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      </Wrap>
    </Band>
  );
}

const Fallback = ({ what }: { what: string }) => <p className="m-0 rounded-card bg-peach p-4 text-ink">{what} failed to load. This message is its designed fallback.</p>;
const Wait = () => <Loader label="Loading" />;

const DEMO_STEPS: StageStep[] = [
  { id: "session", label: "stage_session", mode: "arrive" },
  { id: "extract", label: "stage_reading", mode: "reading" },
  { id: "facts", label: "stage_saving", mode: "saving" },
  { id: "check", label: "stage_checking", mode: "checking" },
];

/** The claim flow's work stage, with a picker for the request in flight (in the app the real request decides). */

/* A plan shaped like the API's health plan (decoration-free sample text), for the route demo. */
const B = (en: string) => ({ en, hi: en });
const pi = (p: Partial<PlanItem> = {}): PlanItem => ({
  key: null, rule_id: null, text: B("What to do at this step."), quote: null, page_no: null, source_id: null,
  source_title: null, source_label: null, date: null, date_label: null, link: null, ...p,
});
const demoFinding = (verdict: Finding["verdict"], rule_id: string): Finding => ({
  rule_id, rule_version: 1, verdict, reason: null, rule_quote: "", source_sha256: "", page_no: null, facts_used: {},
  question_en: null, question_hi: null, action_en: null, action_hi: null,
});
/** sample findings for the one-picture chart (two challengeable, one needs info, one consistent) */
const DEMO_FINDINGS: Finding[] = [demoFinding("CHALLENGEABLE", "MORATORIUM_60M"), demoFinding("CHALLENGEABLE", "PED_DISCLOSURE"), demoFinding("NEED_INFO", "WAITING_30D"), demoFinding("CONSISTENT", "ROOM_RENT")];

const DEMO_PLAN: Plan = {
  kind: "health", supported: true, product_line: "health", unverified: null, title: B("Your plan"), text: B(""), verified: true,
  steps: [
    { id: "case", title: B("Your case"), items: [pi()] },
    { id: "findings", title: B("What the check found"), items: [pi({ rule_id: "MORATORIUM_60M", quote: "Sample quoted rule.", page_no: 8 })] },
    { id: "ask", title: B("What to ask your insurer for"), items: [pi({ quote: "Sample quoted rule.", page_no: 4 }), pi()] },
    { id: "letter", title: B("Send your grievance letter"), items: [pi({ date: { iso: "2026-11-16", display: "16/11/2026" }, date_label: B("Reply due by") })] },
    { id: "ombudsman", title: B("If there is no reply, or it does not settle the matter: Insurance Ombudsman"), items: [pi({ quote: "Sample quoted rule.", page_no: 3 })] },
    { id: "commission", title: B("If your claim is larger than the Ombudsman's limit"), items: [pi()] },
  ],
};
const DEMO_DL = {
  available: true,
  letter_date: { iso: "2026-11-02", display: "02/11/2026" },
  insurer_reply_by: { iso: "2026-11-16", display: "16/11/2026" },
  ombudsman_earliest: { iso: "2026-12-02", display: "02/12/2026" },
  ombudsman_latest: { iso: "2027-11-02", display: "02/11/2027" },
};

/* The claim flow's page change on two sample sheets (the real one is in CheckClaim.tsx). */
function TumbleDemo() {
  const [i, setI] = useState(0);
  const [dir, setDir] = useState<1 | -1>(1);
  const reduce = useReducedMotion();
  const pages = ["1. Upload your documents", "2. Confirm what we read", "3. Your result"];
  const move = (d: 1 | -1) => {
    setDir(d);
    setI((n) => Math.min(2, Math.max(0, n + d)));
  };
  return (
    <div className="wf">
      <div className="mb-6 flex gap-3">
        <button type="button" className="secondary" onClick={() => move(-1)} disabled={i === 0}>Back</button>
        <button type="button" onClick={() => move(1)} disabled={i === 2}>Next</button>
      </div>
      <div className="desk mt-6">
        <Tumble view={String(i)} dir={dir} reduce={!!reduce}>
          <motion.div
            key={i}
            className="sheet"
            {...(reduce ? {} : dir === 1
              ? { initial: { opacity: 0, y: -22, scale: 0.95 }, animate: { opacity: 1, y: 0, scale: 1 }, transition: { duration: 0.6, delay: 0.16 } }
              : { initial: { opacity: 0, rotateX: -70 }, animate: { opacity: 1, rotateX: 0 }, transition: { type: "spring", stiffness: 140, damping: 16 }, style: { transformPerspective: 1600, originY: 1 } })}
          >
            <div className="p-8">
              <h3 className="m-0 font-display text-h2">{pages[i]}</h3>
              <p className="mt-3">Sample sheet. Next: it tips over its bottom edge and the next slides up. Back: the earlier one stands up again.</p>
              <div className="mt-6 h-40 rounded-card bg-peach" />
            </div>
          </motion.div>
        </Tumble>
      </div>
    </div>
  );
}

function StageDemo() {
  const [current, setCurrent] = useState("extract");
  const [slow, setSlow] = useState(false);
  return (
    <div className="wf mx-auto max-w-[60rem]">
      <div className="mb-4 flex flex-wrap gap-2">
        {DEMO_STEPS.map((s) => (
          <button key={s.id} type="button" aria-pressed={current === s.id} onClick={() => setCurrent(s.id)} className="min-h-11 cursor-pointer rounded-full border border-line-strong bg-paper px-4 text-control text-ink aria-pressed:border-action aria-pressed:bg-action aria-pressed:text-on-ink">
            {s.mode}
          </button>
        ))}
        <button type="button" aria-pressed={slow} onClick={() => setSlow((v) => !v)} className="min-h-11 cursor-pointer rounded-full border border-line-strong bg-paper px-4 text-control text-ink aria-pressed:border-action aria-pressed:bg-action aria-pressed:text-on-ink">
          slow server
        </button>
      </div>
      <WorkStage steps={DEMO_STEPS} current={current} slow={slow} />
    </div>
  );
}

/** Dev-only: every installed Aceternity component (all nine), rendered with real Bima Sarthi content, so it can be checked by eye. */
export default function DevComponents() {
  const reduce = usePrefersReducedMotion();
  const stage = useRef<HTMLDivElement>(null);
  const parallaxStage = useRef<HTMLDivElement>(null);
  const [round, setRound] = useState(0);
  const [picked, setPicked] = useState<string[]>([]);
  const sky = useSkyAnimation();
  const nav = typeof navigator !== "undefined" ? navigator.userAgent : "";
  const safariLike = /Safari/.test(nav) && !/Chrome|Chromium|Edg|OPR/.test(nav);
  const backdropUrl = typeof CSS !== "undefined" && CSS.supports?.("backdrop-filter", "url(#x)");
  const slides = SCENARIOS.map((s) => ({ title: s.title, button: "Open", src: ART[s.art], alt: s.artAlt, onSelect: () => setRound((r) => r + 1) }));
  const nv = (typeof navigator !== "undefined" ? navigator : {}) as Navigator & { deviceMemory?: number };

  return (
    <>
      <Band tone="peach" pad="tight" as="header">
        <Wrap width="wide">
          <h1 tabIndex={-1} data-page-heading className="m-0 font-display text-h1 font-medium text-ink">
            Installed components
          </h1>
          <p className="mb-0 mt-3">
            <Tag tone="warm">Dev only</Tag>
          </p>
          <p className="mt-3 max-w-[68ch]">
            The nine Aceternity components, installed from the registry and shown with our own artwork and colours. This page holds no user data and is not linked from the site.
          </p>
          <dl className="mt-4 grid max-w-xl grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-control">
            <dt className="font-semibold">WebGL available</dt>
            <dd className="m-0">{String(hasWebGL())}</dd>
            <dt className="font-semibold">Reduced motion</dt>
            <dd className="m-0">{String(reduce)}</dd>
            <dt className="font-semibold">Low-power device (cores {nv.hardwareConcurrency ?? "?"}, memory {nv.deviceMemory ?? "?"} GB)</dt>
            <dd className="m-0">{String(isLowPower())}</dd>
            <dt className="font-semibold">backdrop-filter: url()</dt>
            <dd className="m-0">{String(!!backdropUrl)}</dd>
            <dt className="font-semibold">Safari-like (glass falls back)</dt>
            <dd className="m-0">{String(safariLike)}</dd>
          </dl>
        </Wrap>
      </Band>

      <Panel
        id="d-glass"
        title="1. LiquidGlass"
        check={[
          "In Chromium the rim of each lens bends the artwork behind it, with a slight colour split; in Safari and Firefox it is frosted glass instead.",
          "The right-hand lens can be dragged inside the artwork. With reduced motion on, it cannot.",
          "Text inside stays readable (it sits on a solid ink plate).",
        ]}
      >
        <div ref={stage} className="relative isolate h-[26rem] overflow-hidden rounded-card bg-peach" style={{ backgroundImage: `url(${ART.dossier})`, backgroundSize: "cover", backgroundPosition: "center" }}>
          <Boundary fallback={<Fallback what="Glass" />}>
            <Suspense fallback={<Wait />}>
              <LiquidGlass radius={32} bevelDepth={14} scale={40} aberration={4} frost={0.4} tint={0.1} className="absolute left-6 top-6 size-40 ring-1 ring-white/30" />
              <GlassChip constraints={stage} className="bottom-8 right-6 max-w-xs">
                Rules decide the verdict. Models only read your documents.
              </GlassChip>
            </Suspense>
          </Boundary>
        </div>
      </Panel>

      <Panel
        id="d-chromatic"
        title="2. ChromaticImage"
        tone="peach"
        check={[
          "Left: move the pointer over the image: it tilts in perspective, warps slightly and splits colour at the edges, then settles when you leave.",
          "Right: the plain-image fallback (reduced motion, no WebGL, low-power sky off). Same artwork, same alt text.",
          "Resize the window: the canvas follows (ResizeObserver).",
        ]}
      >
        <div className="grid gap-8 sm:grid-cols-2">
          <ArtworkImage src={ART.dossier} alt="Illustration: a rejection letter, a verdict stamp, a folded policy schedule and a gold seal on a soft peach and sky-blue background." className="mx-auto aspect-[4/5] w-full max-w-sm rounded-card shadow-stage" />
          <ArtworkImage plain src={ART.dossier} alt="Illustration: the same dossier, shown as the plain-image fallback." className="mx-auto aspect-[4/5] w-full max-w-sm rounded-card shadow-stage" />
        </div>
      </Panel>

      <Panel
        id="d-carousel"
        title="3. Carousel"
        check={["Arrows and clicking a neighbouring slide change the slide; the arrows are keyboard-focusable with a visible ring.", `The slide button runs an action (pressed ${round} times).`, "Titles stay legible on the artwork."]}
      >
        <div className="relative overflow-hidden rounded-card bg-ink pb-24 pt-10">
          <Boundary fallback={<Fallback what="Carousel" />}>
            <Suspense fallback={<Wait />}>
              <Carousel slides={slides} label="Illustrative scenarios" />
            </Suspense>
          </Boundary>
        </div>
      </Panel>

      <Panel id="d-cards" title="4. DraggableCard" tone="peach" check={["Drag a card: it tilts with the pointer and settles with a spring. With reduced motion on, cards do not move.", "All text is readable without dragging (the cards sit side by side at rest)."]}>
        <div className="hidden xl:block">
          <Boundary fallback={null}>
            <Suspense fallback={<Wait />}>
              <DraggableScenarios scenarios={SCENARIOS} />
            </Suspense>
          </Boundary>
        </div>
        <p className="m-0 xl:hidden">The draggable desk shows from 1280 px wide. Below that the scenarios appear as a plain list on the landing page.</p>
      </Panel>

      <Panel
        id="d-parallax"
        title="5. ParallaxHeroImages"
        check={[
          "Move the pointer: the four tiles drift by different amounts (depth layers) and ease with a spring.",
          "On a touch screen, and with reduced motion on, the tiles sit still and appear without the blur-in.",
          "Each tile has alt text; the tiles never cover the page heading above.",
        ]}
      >
        <div ref={parallaxStage} className="relative h-[28rem] overflow-hidden rounded-card bg-[linear-gradient(180deg,var(--color-sky-pale),var(--color-peach))]">
          <Boundary fallback={<Fallback what="Parallax" />}>
            <Suspense fallback={<Wait />}>
              <ParallaxHeroImages
                images={[ART.letter, ART.medical, ART.evidence, ART.schedule]}
                alts={["A letter with a highlighted passage.", "A medical record sheet.", "A magnifying glass over a quoted passage.", "A policy schedule with banded rows."]}
                positions={["top-left", "top-right", "bottom-left", "bottom-right"]}
                imageClassName="h-24 w-32 sm:h-32 sm:w-44 md:h-40 md:w-56"
              />
            </Suspense>
          </Boundary>
          <p className="absolute left-1/2 top-1/2 m-0 -translate-x-1/2 -translate-y-1/2 rounded-card bg-ivory/90 px-5 py-3 text-center font-display text-h3 text-ink">Four depth layers</p>
        </div>
      </Panel>

      <Panel
        id="d-upload"
        title="6. FileUpload"
        tone="peach"
        check={[
          "Click the area, press Enter or Space while it is focused, or drop a file on it: the file card appears (name, size, type, date).",
          "The dummy onChange below lists the names it received. Agent 3b wires this to the claim flow (props: onChange, title, hint, dropLabel, accept, multiple).",
          "Nothing is uploaded from this page: files stay in the browser.",
        ]}
      >
        <div className="mx-auto max-w-2xl">
          <Boundary fallback={<Fallback what="File upload" />}>
            <Suspense fallback={<Wait />}>
              <FileUpload onChange={(files) => setPicked(files.map((f) => f.name))} title="Add your documents" hint="Drop a photo or PDF here, or press to choose a file" dropLabel="Drop it here" />
            </Suspense>
          </Boundary>
          <p className="mt-3 text-control">onChange received: {picked.length ? picked.join(", ") : "nothing yet"}</p>
        </div>
      </Panel>

      <Panel
        id="d-route"
        title="Plan: the route map, the deadline chart, the noticeable action"
        check={[
          "the ink plate shows Parth's ring shader in violet, saffron and periwinkle, top right; the words never sit on a ring",
          "stops rise in one by one; a decision card sits in front of the Ombudsman and the larger-claim steps",
          "press a stop: the porcelain marker slides to it and the page scrolls to that step's detail; arrow keys walk the stops",
          "the deadline bars grow from their start dates and today's marker drops in; the button glows, a light runs round its edge, it leans to the pointer",
          "reduced motion: still rings, no rise, no growth, no glow movement",
        ]}
      >
        <div className="wf">
          <p className="mb-6">
            <Spark>
              <button type="button">Run the check</button>
            </Spark>
          </p>
          <FindingsChart findings={DEMO_FINDINGS} ground="pre_existing_disease" />
          <DeadlineTimeline d={DEMO_DL} />
          <PlanSection plan={DEMO_PLAN} />
        </div>
        <div className="mt-12" id="d-tumble">
          <TumbleDemo />
        </div>
      </Panel>

      <Panel
        id="d-stage"
        title="Claim flow: the work stage"
        check={[
          "reading: a saffron scan line passes down the front glass sheet and each line glows as it is read",
          "saving: the fan closes into a stack; checking: a glass lens steps line by line and passed lines turn indigo",
          "drag the sheets (mouse) to turn the file; it springs back; the pointer anywhere on the panel tilts it a little",
          "the CSS 3D version shows first and the WebGL canvas fades in over it; with WebGL off only the CSS version shows",
          "reduced motion: one still frame, no scan, no drag, no aurora drift",
        ]}
      >
        <StageDemo />
      </Panel>

      <Band tone="ink" pad="none" labelledBy="d-lamp" as="section">
        <Boundary fallback={<Wrap className="py-16"><Fallback what="Lamp" /></Wrap>}>
          <Suspense fallback={<Wait />}>
            <LampContainer className="min-h-[40rem] rounded-none">
              <h2 id="d-lamp" className="m-0 text-center font-display text-h1 font-medium text-on-ink">
                7. Lamp: a guiding light
              </h2>
              <p className="mx-auto mt-4 max-w-[48ch] text-center text-on-ink">Warm sunlight instead of cyan; the two beams widen as the section enters the screen.</p>
            </LampContainer>
          </Suspense>
        </Boundary>
        <Wrap width="wide" className="pb-8 pt-4">
          <p className="m-0 max-w-[70ch] text-on-ink-soft">
            What to check: beams, glow and line are apricot and champagne (no cyan); the heading is readable; with reduced motion the beams are already at full width.
          </p>
        </Wrap>
      </Band>

      <Panel
        id="d-timeline"
        title="8. Timeline"
        check={["Scroll: the line beside the steps fills as each step passes the upper part of the screen.", "The step titles stay pinned beside their content on wide screens; on phones the title sits above the content.", "With reduced motion the line is drawn full and nothing moves."]}
      >
        <Boundary fallback={<Fallback what="Timeline" />}>
          <Suspense fallback={<Wait />}>
            <Timeline
              heading="Three of the six steps"
              data={STAGES.slice(0, 3).map((s, i) => ({
                title: s.title,
                number: i + 1,
                content: (
                  <div className="grid items-start gap-6 xl:grid-cols-[1.1fr_1fr]">
                    <p className="m-0 max-w-[58ch]">{s.short}</p>
                    <img src={ART[s.art]} alt={s.artAlt} width={420} height={420} loading="lazy" className="aspect-square w-full max-w-xs rounded-card shadow-lift" />
                  </div>
                ),
              }))}
            />
          </Suspense>
        </Boundary>
      </Panel>

      <Panel
        id="d-cloud"
        title="9. CloudShader"
        tone="peach"
        check={[
          "Left: the live WebGL sky. Soft dusty-pink and peach clouds drift; the sun glow sits upper right. Not saturated orange, not pink fantasy.",
          "Right: the static sunset fallback, built from the same palette (src/design/atmosphere.ts).",
          "The toggle persists in the browser (key bimasarthi.sky, see hooks/useSkyPreference.ts). The clouds pause when scrolled off screen and when the tab is hidden; with reduced motion one still frame is drawn.",
          `Now: ${sky.useShader ? "shader mounted" : "static sky"}, animating: ${String(sky.animating)}.`,
        ]}
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <figure className="m-0">
            <div className="relative isolate h-[22rem] overflow-hidden rounded-card">
              <SkyBackdrop shader={sky.useShader} onUnavailable={sky.markUnavailable} className="z-0" />
              <p className="absolute inset-x-6 bottom-6 m-0 rounded-card bg-ivory/80 px-4 py-3 text-ink">Ink text on an ivory scrim keeps 4.5:1 or more over the darkest cloud.</p>
            </div>
            <figcaption className="mt-2 text-control text-ink-soft">CloudShader (or its fallback, if WebGL is off)</figcaption>
          </figure>
          <figure className="m-0">
            <div className="relative isolate h-[22rem] overflow-hidden rounded-card">
              <SkyBackdrop shader={false} className="z-0" />
              <p className="absolute inset-x-6 bottom-6 m-0 rounded-card bg-ivory/80 px-4 py-3 text-ink">The static fallback: same palette, no WebGL.</p>
            </div>
            <figcaption className="mt-2 text-control text-ink-soft">Static sunset fallback</figcaption>
          </figure>
        </div>
        {sky.canToggle ? <SkyToggle pressed={sky.useShader} onToggle={sky.toggle} className="mt-5" /> : <p className="mt-5 text-control">The toggle is hidden: WebGL is unavailable or reduced motion is on.</p>}
      </Panel>
    </>
  );
}
