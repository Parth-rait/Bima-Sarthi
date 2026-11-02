import { Suspense, lazy } from "react";
import { Boundary } from "@/components/ds/Boundary";
import { Button } from "@/components/ds/Button";
import { Loader } from "@/components/ds/Loader";
import { Band, Wrap } from "@/components/ds/Section";
import { ART } from "@/content/art";
import { STAGES } from "@/content/stages";
import { LampContainer } from "@/components/ui/lamp";
import { useSession } from "@/state/store";

// This route is already its own lazy chunk, so the Lamp (small, CSS-only) is imported statically: the page's <h1> lives inside it
// and must exist on first render so route focus lands on it. The Timeline is a further lazy chunk; StaticSteps shows the same six steps without it.
const Timeline = lazy(() => import("@/components/ui/timeline").then((m) => ({ default: m.Timeline })));

const LEAD = "Six steps, from the photo of a letter to a plan you can act on. You stay in control of every step, and the rules, not a model, decide each verdict.";

function IntroText() {
  const { state, t } = useSession();
  return (
    <div className="max-w-3xl text-center">
      <h1 tabIndex={-1} data-page-heading className="m-0 font-display text-h1 font-medium text-on-ink">
        How it works
      </h1>
      <p className="mx-auto mt-5 max-w-[56ch] text-lead text-on-ink">{LEAD}</p>
      {state.lang === "hi" ? <p role="note" className="mx-auto mt-4 max-w-[56ch] text-[0.9375rem] text-on-ink">{t("editorial_note")}</p> : null}
    </div>
  );
}

function StepContent({ i }: { i: number }) {
  const s = STAGES[i];
  return (
    <article id={s.id} tabIndex={-1} aria-label={s.title} className="grid items-start gap-6 xl:grid-cols-[1.15fr_1fr] xl:gap-10">
      <div>
        {s.long.map((p) => (
          <p key={p} className="mb-0 mt-0 max-w-[58ch] [&:not(:first-child)]:mt-4">
            {p}
          </p>
        ))}
        <p className="mt-5 max-w-[58ch] border-t border-gold pt-3">
          <strong className="text-ink">Your part: </strong>
          {s.yourPart}
        </p>
      </div>
      <img src={ART[s.art]} alt={s.artAlt} width={420} height={420} loading="lazy" className="aspect-square w-full max-w-sm rounded-card shadow-lift xl:justify-self-end" />
    </article>
  );
}

/** Without the Timeline chunk: the same six steps as a plain ordered list, with the same content. */
function StaticSteps() {
  return (
    <ol className="m-0 list-none space-y-14 p-0">
      {STAGES.map((s, i) => (
        <li key={s.id}>
          <span aria-hidden="true" className="mb-1 block font-display text-[2.5rem] leading-none text-ink-soft">{i + 1}</span>
          <h3 className="m-0 mb-4 font-display text-h2 font-medium text-ink">
            <span className="sr-only">Step {i + 1}: </span>
            {s.title}
          </h3>
          <StepContent i={i} />
        </li>
      ))}
    </ol>
  );
}

export default function HowItWorks() {
  const { t } = useSession();
  const data = STAGES.map((s, i) => ({ title: s.title, number: i + 1, content: <StepContent i={i} /> }));
  return (
    <>
      <Band tone="ink" pad="none" as="header">
        <LampContainer className="min-h-[46rem] rounded-none md:min-h-[50rem]">
          <IntroText />
        </LampContainer>
      </Band>

      <Band tone="ivory" labelledBy="steps-h" className="pt-[var(--section-y-tight)]">
        <Wrap width="wide">
          <Boundary fallback={<StaticSteps />}>
            <Suspense
              fallback={
                <div className="grid min-h-[20rem] place-items-center">
                  <Loader label={t("loading")} />
                </div>
              }
            >
              <Timeline headingId="steps-h" heading="The six steps, in order" description="Scroll down: the line fills as you pass each step. Every step says what happens and what, if anything, you do." data={data} />
            </Suspense>
          </Boundary>
        </Wrap>
      </Band>

      <Band tone="sky" labelledBy="how-cta-h">
        <Wrap width="wide" className="flex flex-wrap items-center justify-between gap-6">
          <h2 id="how-cta-h" className="m-0 max-w-[24ch] font-display text-h1 font-medium text-ink">
            See it with your own letter.
          </h2>
          <div className="flex flex-wrap gap-3">
            <Button to="/check-claim" variant="primary" size="lg">
              {t("nav_check")}
            </Button>
            <Button to="/help" variant="secondary" size="lg">
              {t("nav_help")}
            </Button>
          </div>
        </Wrap>
      </Band>
    </>
  );
}
