import { Suspense, lazy, useRef } from "react";
import { Link } from "react-router";
import { Accordion } from "@/components/ds/Accordion";
import { Boundary } from "@/components/ds/Boundary";
import { Button } from "@/components/ds/Button";
import { Band, Grid12, Prose, Wrap } from "@/components/ds/Section";
import { StatusBadge, Tag } from "@/components/ds/StatusBadge";
import { ArtworkImage } from "@/components/landing/ArtworkImage";
import { SkyBackdrop, SkyToggle } from "@/components/landing/SkyBackdrop";
import { ART } from "@/content/art";
import { FAQ } from "@/content/faq";
import { SCENARIOS } from "@/content/scenarios";
import { STAGES } from "@/content/stages";
import { SCRIM } from "@/design/atmosphere";
import { useMediaQuery } from "@/hooks/useMedia";
import { useSkyAnimation } from "@/hooks/useSkyPreference";
import { useSession } from "@/state/store";

const GlassChip = lazy(() => import("@/components/landing/GlassChip"));
const ParallaxHeroImages = lazy(() => import("@/components/ui/parallax-hero-images").then((m) => ({ default: m.ParallaxHeroImages })));
const DraggableScenarios = lazy(() => import("@/components/landing/DraggableScenarios"));

const GLASS_TEXT = "Rules decide the verdict. Models only read your documents.";

/** The static version of the glass chip: same words on the same plate, no glass, no dragging. */
function ChipPlate({ className }: { className?: string }) {
  return (
    <div className={`absolute z-30 rounded-[26px] border border-ivory/40 shadow-stage ${className ?? ""}`}>
      <div className="m-1.5 rounded-[20px] bg-ink/90 px-4 py-3 text-on-ink">{GLASS_TEXT}</div>
    </div>
  );
}

const ivory = (a: number) => `rgba(251, 246, 238, ${a})`;

/** Hero: the sky (CloudShader or the static sunset) fills the band edge to edge; message left, art composition right. */
function Hero() {
  const { state, t } = useSession();
  const sky = useSkyAnimation();
  const stage = useRef<HTMLDivElement>(null);
  const tiles = useMediaQuery("(min-width: 40rem)");
  const chipPos = "bottom-2 left-1 max-w-[16rem] sm:bottom-6 sm:left-0 sm:max-w-[17rem] lg:max-w-xs";
  return (
    <section
      aria-labelledby="hero-h"
      data-layout="band"
      data-tone="sky"
      className="relative isolate -mt-[var(--nav-h)] flex min-h-[min(100svh,60rem)] items-center overflow-hidden pb-[var(--section-y-tight)] pt-[calc(var(--nav-h)+2.5rem)] text-ink"
    >
      <SkyBackdrop shader={sky.useShader} onUnavailable={sky.markUnavailable} />
      {/* scrims: ivory washes that keep ink text >= 4.5:1 over the darkest cloud shadow (checked by npm run contrast) */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-40" style={{ background: `linear-gradient(180deg, ${ivory(SCRIM.navAlpha)}, transparent)` }} />
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 lg:hidden" style={{ background: `linear-gradient(180deg, ${ivory(SCRIM.alpha)} 0%, ${ivory(SCRIM.alpha)} 56%, transparent 100%)` }} />
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 hidden lg:block" style={{ background: `linear-gradient(90deg, ${ivory(SCRIM.alpha)} 0%, ${ivory(SCRIM.alpha)} 54%, transparent 76%)` }} />
      <Wrap width="wide">
        <Grid12 className="items-center">
          <div className="lg:col-span-6">
            <h1 id="hero-h" tabIndex={-1} data-page-heading className="m-0 max-w-[16ch] font-display text-display font-medium text-balance text-ink">
              Your health claim deserves a fair explanation.
            </h1>
            <p className="mt-6 max-w-[34rem] text-lead text-ink">
              Understand why your health-insurance claim was rejected, examine the relevant rules and discover what you can do next.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <Button to="/check-claim" variant="primary" size="lg">
                {t("nav_check")}
              </Button>
              <Button to="/how-it-works" variant="secondary" size="lg">
                {t("nav_how")}
              </Button>
            </div>
            {state.lang === "hi" ? <p role="note" className="mt-6 max-w-[34rem] text-control text-ink">{t("editorial_note")}</p> : null}
            <p className="mt-8 max-w-[34rem] text-control text-ink">No account needed. An independent project: not an insurer, not the regulator, not a lawyer.</p>
            {sky.canToggle ? <SkyToggle pressed={sky.useShader} onToggle={sky.toggle} className="mt-5" /> : null}
          </div>

          <div ref={stage} className="relative mx-auto h-[24rem] w-full max-w-xl sm:h-[31rem] lg:col-span-6 lg:h-[min(37rem,72vh)] lg:max-w-none">
            {tiles ? (
              <Boundary fallback={null}>
                <Suspense fallback={null}>
                  <ParallaxHeroImages
                    className="z-20"
                    images={[ART.letter, ART.medical, ART.schedule]}
                    alts={[
                      "Illustration: a letter with a highlighted quoted passage and a rose-coloured stamp.",
                      "Illustration: a medical record sheet with a heartbeat line and a small cross.",
                      "Illustration: a policy schedule with banded rows and a gold seal.",
                    ]}
                    positions={["top-left", "top-right", "bottom-right"]}
                    imageClassName="h-24 w-32 sm:h-28 sm:w-36 md:h-32 md:w-44 lg:h-36 lg:w-48"
                  />
                </Suspense>
              </Boundary>
            ) : null}
            <div className="absolute left-1/2 top-1/2 z-10 aspect-[4/5] h-[82%] -translate-x-1/2 -translate-y-1/2">
              <ArtworkImage
                src={ART.dossier}
                plain={!sky.animating}
                alt="Illustration: a rejection letter with a highlighted quoted passage, a verdict stamp, a folded policy schedule and a gold seal, laid out on a soft peach and sky-blue background."
                className="size-full rounded-card shadow-stage"
                width={1200}
                height={1500}
              />
            </div>
            <Boundary fallback={<ChipPlate className={chipPos} />}>
              <Suspense fallback={<ChipPlate className={chipPos} />}>
                <GlassChip constraints={stage} className={chipPos}>
                  {GLASS_TEXT}
                </GlassChip>
              </Suspense>
            </Boundary>
          </div>
        </Grid12>
      </Wrap>
    </section>
  );
}

/** Why rejections are hard: heading + prose left, the one verified figure large on the right. */
function Problem() {
  return (
    <Band tone="ivory" labelledBy="problem-h">
      <Wrap width="wide">
        <Grid12 className="items-center">
          <div className="reveal lg:col-span-6">
            <h2 id="problem-h" className="m-0 max-w-[22ch] font-display text-h2 font-medium text-ink">
              A rejection letter states a decision. Checking it takes three documents side by side.
            </h2>
            <Prose className="mt-5 text-lead">
              To see whether an insurer followed the rules you have to read the letter, the policy it relies on and the regulation behind it, and then work out which dates matter. That is slow, and it is hard to do while worried about a hospital bill.
            </Prose>
          </div>
          <figure className="reveal m-0 border-t border-gold pt-6 lg:col-span-5 lg:col-start-8">
            <blockquote className="m-0 font-display text-h3 font-medium leading-snug text-ink">
              The Council for Insurance Ombudsmen recorded{" "}
              <span className="block py-2 text-[clamp(3.25rem,7vw,6rem)] font-medium leading-none tracking-tight">31,490</span>
              complaints about health insurance in 2023-24.
            </blockquote>
            <figcaption className="mt-4 max-w-[52ch] text-control text-ink-soft">
              Source: CIO Annual Report 2023-24 (secondary source). It counts complaints, not rejections, and says nothing about who was right.
            </figcaption>
          </figure>
        </Grid12>
      </Wrap>
    </Band>
  );
}

const DOES = [
  ["Reads your documents", "Photos or PDFs of the rejection letter and, if you have it, the policy. A model reads the pages and proposes facts, each with the line it came from."],
  ["Asks you to confirm", "You check every fact against its source line. Facts marked Please confirm must be confirmed before the check runs."],
  ["Applies written rules", "A rule engine compares the confirmed facts with rule cards. Each card quotes its regulation, and the quote is checked against the stored source page."],
  ["Explains what to do next", "Deadlines counted from the dates you enter, a plan, the documents to request, and a grievance letter to download when there is something to raise. The app never sends anything for you."],
] as const;

function WhatWeDo() {
  return (
    <Band tone="peach" labelledBy="does-h">
      <Wrap width="wide">
        <Grid12>
          <div className="reveal lg:col-span-4">
            <h2 id="does-h" className="m-0 font-display text-h2 font-medium text-ink">
              What Bima Sarthi does
            </h2>
            <p className="mt-4 max-w-[36ch]">Four things, in this order, and nothing else.</p>
          </div>
          <ol className="reveal m-0 grid list-none gap-x-[var(--grid-gap)] gap-y-10 p-0 sm:grid-cols-2 lg:col-span-8">
            {DOES.map(([title, body], i) => (
              <li key={title} className="border-t border-line-strong/40 pt-4">
                <p aria-hidden="true" className="m-0 font-display text-[1.75rem] leading-none text-ink-soft">
                  {String(i + 1).padStart(2, "0")}
                </p>
                <h3 className="m-0 mt-3 font-display text-h3 font-medium text-ink">{title}</h3>
                <p className="mb-0 mt-2 max-w-[44ch]">{body}</p>
              </li>
            ))}
          </ol>
        </Grid12>
      </Wrap>
    </Band>
  );
}

/** The process in short: an atmospheric (CSS-only) band, six numbered steps across the full well. */
function HowPreview() {
  const { t } = useSession();
  return (
    <Band tone="sky" labelledBy="how-h">
      <Wrap width="wide">
        <div className="reveal flex flex-wrap items-end justify-between gap-6">
          <h2 id="how-h" className="m-0 max-w-[24ch] font-display text-h2 font-medium text-ink">
            Six stages, and the last word belongs to the rules
          </h2>
          <Button to="/how-it-works" variant="secondary">
            {t("lnd_walk")}
          </Button>
        </div>
        <ol className="reveal m-0 mt-12 grid list-none gap-x-[var(--grid-gap)] gap-y-10 p-0 sm:grid-cols-2 lg:grid-cols-3">
          {STAGES.map((s, i) => (
            <li key={s.id} className="border-t border-ink/25 pt-4">
              <div className="flex items-baseline gap-3">
                <span aria-hidden="true" className="font-display text-[2.25rem] leading-none text-ink">
                  {i + 1}
                </span>
                <h3 className="m-0 font-display text-h3 font-medium text-ink">
                  <span className="sr-only">Stage {i + 1}: </span>
                  {s.title}
                </h3>
              </div>
              <p className="mb-0 mt-3 max-w-[40ch]">{s.short}</p>
            </li>
          ))}
        </ol>
      </Wrap>
    </Band>
  );
}

/** Documents needed: art left, list right (the layout flips against the section above). */
function Documents() {
  return (
    <Band tone="ivory" labelledBy="docs-h">
      <Wrap width="wide">
        <Grid12 className="items-center">
          <div className="reveal lg:col-span-5">
            <img src={ART.letter} alt="Illustration: a letter with a highlighted quoted paragraph and a rose-coloured stamp." width={640} height={640} loading="lazy" className="mx-auto aspect-square w-full max-w-lg rounded-card shadow-lift" />
          </div>
          <div className="reveal lg:col-span-6 lg:col-start-7">
            <h2 id="docs-h" className="m-0 font-display text-h2 font-medium text-ink">
              Have these ready
            </h2>
            <ul className="mt-6 list-none space-y-6 p-0">
              <li className="border-t border-gold pt-4">
                <p className="m-0 flex flex-wrap items-center gap-2 font-semibold text-ink">
                  The insurer&apos;s rejection or settlement letter <Tag tone="plain">Required</Tag>
                </p>
                <p className="m-0 mt-1">This is what the check starts from. Include every page.</p>
              </li>
              <li className="border-t border-gold pt-4">
                <p className="m-0 flex flex-wrap items-center gap-2 font-semibold text-ink">
                  The policy schedule or policy document <Tag tone="plain">Recommended</Tag>
                </p>
                <p className="m-0 mt-1">If you add it, its key terms are shown beside the words they came from. The check works without it.</p>
              </li>
            </ul>
            <p className="mt-6 max-w-[52ch] text-ink-soft">
              JPG, PNG or PDF. Up to 20 pages and 25 MB in total. Photos can be up to 40 megapixels. Lay the page flat in good light so every line is readable.
            </p>
          </div>
        </Grid12>
      </Wrap>
    </Band>
  );
}

/** What the assessment provides: the one ink band on the page (evening). Verdicts as shape + word + sentence. */
function Assessment() {
  const { t } = useSession();
  const provides = ["A verdict for each finding, with the rule it compared and the quote and page it came from.", "Deadlines counted only from dates you entered.", "A plan: what to ask the insurer, which documents to request, where to escalate.", "A grievance letter to download when there is something to raise. The app never sends anything for you."];
  return (
    <Band tone="ink" labelledBy="struct-h">
      <Wrap width="wide">
        <Grid12>
          <div className="reveal lg:col-span-5">
            <h2 id="struct-h" className="m-0 max-w-[18ch] font-display text-h2 font-medium text-on-ink">
              What the assessment gives you
            </h2>
            <ul className="mt-6 list-none space-y-3 p-0 text-on-ink-soft">
              {provides.map((p) => (
                <li key={p} className="border-t border-on-ink-soft/30 pt-3">
                  {p}
                </li>
              ))}
            </ul>
          </div>
          <div className="reveal lg:col-span-6 lg:col-start-7">
            <p className="m-0 text-on-ink-soft">Each finding gets one of three verdicts, always as a shape, a word and a sentence.</p>
            <div className="mt-6 divide-y divide-on-ink-soft/30">
              {(["CHALLENGEABLE", "NEED_INFO", "CONSISTENT"] as const).map((v) => (
                <div key={v} className="flex flex-wrap items-center gap-x-6 gap-y-2 py-5">
                  <StatusBadge verdict={v} className="shrink-0" />
                  <p className="m-0 min-w-[16rem] flex-1 text-on-ink">{t(v)}</p>
                </div>
              ))}
            </div>
            <p className="mt-6 max-w-[60ch] text-on-ink-soft">
              Consistent is not good news in disguise: it only means this rule gives no ground to challenge. When facts are missing, the app says Need more information instead of guessing.
            </p>
          </div>
        </Grid12>
      </Wrap>
    </Band>
  );
}

function ScenarioList() {
  return (
    <ul className="m-0 list-none divide-y divide-line-strong/30 p-0">
      {SCENARIOS.map((s) => (
        <li key={s.id} className="grid items-center gap-5 py-6 sm:grid-cols-[8rem_1fr] md:grid-cols-[10rem_1fr] md:gap-8">
          <img src={ART[s.art]} alt={s.artAlt} width={160} height={160} loading="lazy" className="aspect-square w-32 rounded-card md:w-40" />
          <div>
            <h3 className="m-0 font-display text-h3 font-medium text-ink">{s.title}</h3>
            <p className="mb-0 mt-2 max-w-[62ch]">{s.body}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function Scenarios() {
  const desk = useMediaQuery("(min-width: 80rem)");
  return (
    <Band tone="peach" labelledBy="scen-h">
      <Wrap width="wide">
        <div className="reveal max-w-[68ch]">
          <h2 id="scen-h" className="m-0 font-display text-h2 font-medium text-ink">
            What it can look like
          </h2>
          <p className="mt-3 text-ink">
            These scenarios are <strong>illustrative</strong>: made up to show what the app asks and shows. They are not real people or real claims, and none has an outcome. Real, cited judgments are on the{" "}
            <Link to="/cases" className="text-ink">
              Real cases
            </Link>{" "}
            page.
          </p>
        </div>
        <div className="reveal mt-10">
          {desk ? (
            <Boundary fallback={<ScenarioList />}>
              <Suspense fallback={<ScenarioList />}>
                <DraggableScenarios scenarios={SCENARIOS} />
              </Suspense>
            </Boundary>
          ) : (
            <ScenarioList />
          )}
        </div>
      </Wrap>
    </Band>
  );
}

function PrivacyStrip() {
  const { t } = useSession();
  const facts = [
    "Your files sit in a temporary server folder and are deleted once the check has run, or after one hour at the latest.",
    "Documents are never written to the database, the model cache or the logs.",
    "There is no account, no sign-in, and this site loads no third-party scripts, fonts or trackers.",
    "The page images are sent to a model provider to be read. Free-tier providers may use inputs, so use sample or redacted documents while the project is being tested.",
    "Nothing here is a trained model of our own: we use existing models only to read and to phrase explanations.",
  ];
  return (
    <Band tone="ivory" labelledBy="priv-h">
      <Wrap width="wide">
        <Grid12>
          <div className="reveal lg:col-span-4">
            <h2 id="priv-h" className="m-0 max-w-[16ch] font-display text-h2 font-medium text-ink">
              Privacy and transparency
            </h2>
            <p className="mt-4 max-w-[40ch]">What the app does with your documents, stated plainly, and what it does not do.</p>
            <Button to="/privacy" variant="secondary" className="mt-6">
              {t("lnd_privacy")}
            </Button>
          </div>
          <ul className="reveal m-0 list-none space-y-4 p-0 lg:col-span-7 lg:col-start-6">
            {facts.map((f) => (
              <li key={f} className="border-t border-line-strong/40 pt-3">
                {f}
              </li>
            ))}
          </ul>
        </Grid12>
      </Wrap>
    </Band>
  );
}

function Faq() {
  const teaser = FAQ.slice(0, 5);
  return (
    <Band id="faq" tone="peach" labelledBy="faq-h">
      <Wrap width="wide">
        <Grid12>
          <div className="reveal lg:col-span-4">
            <h2 id="faq-h" className="m-0 font-display text-h2 font-medium text-ink">
              Frequently asked questions
            </h2>
            <p className="mt-4 max-w-[36ch]">
              More answers, with search, are in the{" "}
              <Link to="/help" className="text-ink">
                Help centre
              </Link>
              .
            </p>
          </div>
          <div className="reveal lg:col-span-7 lg:col-start-6">
            <Accordion items={teaser.map((f) => ({ id: f.id, title: f.q, content: f.a.map((p) => <p key={p} className="m-0 mb-3 max-w-[62ch]">{p}</p>) }))} />
          </div>
        </Grid12>
      </Wrap>
    </Band>
  );
}

function FinalCta() {
  const { t } = useSession();
  return (
    <Band tone="sky" labelledBy="cta-h">
      <Wrap width="wide">
        <div className="reveal flex flex-wrap items-center justify-between gap-8">
          <h2 id="cta-h" className="m-0 max-w-[22ch] font-display text-h1 font-medium text-ink">
            Start with the letter in your hand.
          </h2>
          <Button to="/check-claim" variant="primary" size="lg">
            {t("nav_check")}
          </Button>
        </div>
      </Wrap>
    </Band>
  );
}

export default function Landing() {
  return (
    <>
      <Hero />
      <Problem />
      <WhatWeDo />
      <HowPreview />
      <Documents />
      <Assessment />
      <Scenarios />
      <PrivacyStrip />
      <Faq />
      <FinalCta />
    </>
  );
}
