import { useEffect, useRef } from "react";
import { motion, useReducedMotion } from "motion/react";
import { useService } from "@/app/ServiceStatus";
import { Button } from "@/components/ds/Button";
import { ErrorState } from "@/components/ds/ErrorState";
import { Stepper } from "@/components/ds/Stepper";
import { Band, Wrap } from "@/components/ds/Section";
import { RoleToggle } from "@/components/layout/Seg";
import { ErrorBox } from "@/components/ErrorBox";
import { Tumble } from "@/components/flow/Tumble";
import { EASE } from "@/lib/motion";
import { useSession } from "@/state/store";
import { ConfirmScreen } from "@/screens/ConfirmScreen";
import { DeletedScreen } from "@/screens/DeletedScreen";
import { ResultScreen } from "@/screens/ResultScreen";
import { UploadScreen } from "@/screens/UploadScreen";

/**
 * The working claim flow (upload > confirm > result), re-hosted unchanged in behaviour inside the new shell.
 * Gating, error mapping and the API calls live in the screens and the session store; this page only adds the page header,
 * the service-status notice, the stepper and the step-change focus handling.
 * Layout: a band (full-bleed tone + section rhythm) holding the default well, and inside it the .flow / .desk / .sheet
 * vocabulary that operate.css styles for screen and print.css styles for paper. The page never constrains a screen's width —
 * that is each screen's job, and pinning it here is what left the desktop half empty once.
 */
export default function CheckClaim() {
  const { state, actions, t } = useSession();
  const svc = useService();
  const body = useRef<HTMLDivElement>(null);
  const first = useRef(true);
  const reduce = useReducedMotion();
  // a step change goes the way you are travelling: forward, the sheet falls and the next slides up; back, it stands up again
  const ORDER: Record<string, number> = { upload: 0, confirm: 1, result: 2, deleted: 3, gallery: 0 };
  // decided once per step change (not per render), so a re-render mid-animation never swaps the animation's target
  const travel = useRef({ view: state.view, dir: 1 as 1 | -1 });
  if (travel.current.view !== state.view) {
    travel.current = { view: state.view, dir: (ORDER[state.view] ?? 0) >= (ORDER[travel.current.view] ?? 0) ? 1 : -1 };
  }
  const dir = travel.current.dir;
  // forward: the next sheet slides up to the line from behind the one that falls (Tumble);
  // back: the earlier sheet stands up again from the floor
  const arrive = reduce
    ? {}
    : dir === 1
      ? {
          initial: { opacity: 0, y: -22, scale: 0.95 },
          animate: { opacity: 1, y: 0, scale: 1 },
          transition: { duration: 0.6, ease: EASE, delay: 0.16 },
        }
      : {
          initial: { opacity: 0, rotateX: -70 },
          animate: { opacity: 1, rotateX: 0 },
          transition: { type: "spring" as const, stiffness: 140, damping: 16, mass: 0.9 },
          style: { transformPerspective: 1600, originY: 1 },
        };

  // On a step change inside the page, move focus to the new screen's heading (the route change itself focuses the h1).
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    body.current?.querySelector<HTMLElement>("[data-screen-heading]")?.focus();
    window.scrollTo?.(0, 0);
  }, [state.view]);

  const steps = [
    { id: "upload", text: t("s1") },
    { id: "confirm", text: t("s2") },
    { id: "result", text: t("s3") },
  ];
  const stepped = state.view === "upload" || state.view === "confirm" || state.view === "result";
  const screenTitle = state.view === "upload" ? t("s1") : state.view === "confirm" ? t("s2") : state.view === "result" ? t("s3") : t("deleted_h");

  return (
    <>
      <Band as="header" tone="peach" pad="tight" className="claim-hero border-b border-line">
        <span className="claim-hero-light" aria-hidden="true" />
        <Wrap width="default" className="relative flex flex-wrap items-end justify-between gap-6">
          <div>
            <h1 tabIndex={-1} data-page-heading className="m-0 font-display text-h1 font-medium text-ink">
              {t("nav_check")}
            </h1>
            <p className="mb-0 mt-3 max-w-[52ch] text-lead">{t("tagline")}</p>
          </div>
          <RoleToggle idPrefix="" tone="light" />
        </Wrap>
      </Band>

      <Band as="div" tone="ivory" pad="tight" className="wf">
        <Wrap width="narrow" className="relative">
          <span className="desk-light" aria-hidden="true" />
          <div className="flow" ref={body}>
            {svc.status === "down" ? (
              <ErrorState title={t("svc_title")} what={t("svc_what")} why={t("svc_why")} next={t("svc_next")}>
                <Button variant="secondary" onClick={svc.retry}>
                  {t("svc_retry")}
                </Button>
              </ErrorState>
            ) : null}
            {/* the stepper's tabs meet the sheet's top edge, so they share one flush frame */}
            <div className="frame">
              {stepped ? <Stepper steps={steps} current={state.view} label={t("steps_label")} /> : null}
              <div className="desk">
                <Tumble view={state.view} dir={dir} reduce={!!reduce}>
                  {/* one step replaces another: the new sheet is the real screen from its first frame; the falling copy above it is decoration */}
                  <motion.div key={state.view} className="sheet" {...arrive}>
                    {state.expired ? (
                      <ErrorBox message={t("expired")}>
                        <p>
                          <button type="button" onClick={() => actions.restart()}>
                            {t("again")}
                          </button>
                        </p>
                      </ErrorBox>
                    ) : null}
                    <div className="screen-slot">
                      {state.view === "upload" ? <UploadScreen /> : null}
                      {state.view === "confirm" ? <ConfirmScreen /> : null}
                      {state.view === "result" ? <ResultScreen /> : null}
                      {state.view === "deleted" ? <DeletedScreen /> : null}
                    </div>
                  </motion.div>
                </Tumble>
              </div>
            </div>
          </div>
        </Wrap>
        <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
          {screenTitle}
        </div>
      </Band>
    </>
  );
}
