import { useEffect, useRef } from "react";
import { useService } from "@/app/ServiceStatus";
import { Button } from "@/components/ds/Button";
import { ErrorState } from "@/components/ds/ErrorState";
import { Stepper } from "@/components/ds/Stepper";
import { Container } from "@/components/ds/Section";
import { RoleToggle } from "@/components/layout/Seg";
import { ErrorBox } from "@/components/ErrorBox";
import { useSession } from "@/state/store";
import { ConfirmScreen } from "@/screens/ConfirmScreen";
import { DeletedScreen } from "@/screens/DeletedScreen";
import { ResultScreen } from "@/screens/ResultScreen";
import { UploadScreen } from "@/screens/UploadScreen";

/**
 * The working claim flow (upload > confirm > result), re-hosted unchanged in behaviour inside the new shell.
 * Gating, error mapping and the API calls live in the screens and the session store; this page only adds the page header,
 * the service-status notice, the stepper and the step-change focus handling. STAGE 7 ports the screens to the new components.
 */
export default function CheckClaim() {
  const { state, actions, t } = useSession();
  const svc = useService();
  const body = useRef<HTMLDivElement>(null);
  const first = useRef(true);

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
      <header className="border-b border-line bg-champagne">
        <Container className="flex flex-wrap items-end justify-between gap-6 py-8 md:py-10">
          <div>
            <h1 tabIndex={-1} data-page-heading className="m-0 font-display text-h1 font-medium text-ink">
              {t("nav_check")}
            </h1>
            <p className="mb-0 mt-3 max-w-[52ch] text-lead">{t("tagline")}</p>
          </div>
          <RoleToggle idPrefix="" tone="light" />
        </Container>
      </header>

      <div className="wf bg-ground pb-16" ref={body}>
        <Container className="max-w-4xl pt-6">
          {svc.status === "down" ? (
            <ErrorState title={t("svc_title")} what={t("svc_what")} why={t("svc_why")} next={t("svc_next")} className="mb-6">
              <Button variant="secondary" onClick={svc.retry}>
                {t("svc_retry")}
              </Button>
            </ErrorState>
          ) : null}
          {stepped ? <Stepper steps={steps} current={state.view} label={t("steps_label")} /> : null}
          <div className="desk px-0 md:px-0">
            <div className="sheet">
              {state.expired ? (
                <ErrorBox message={t("expired")}>
                  <p>
                    <button type="button" onClick={() => actions.restart()}>
                      {t("again")}
                    </button>
                  </p>
                </ErrorBox>
              ) : null}
              {state.view === "upload" ? <UploadScreen /> : null}
              {state.view === "confirm" ? <ConfirmScreen /> : null}
              {state.view === "result" ? <ResultScreen /> : null}
              {state.view === "deleted" ? <DeletedScreen /> : null}
            </div>
          </div>
        </Container>
        <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
          {screenTitle}
        </div>
      </div>
    </>
  );
}
