import { useParams } from "react-router";
import { Button } from "@/components/ds/Button";
import { ErrorState } from "@/components/ds/ErrorState";
import { Container } from "@/components/ds/Section";
import { ChecklistSection, DeadlinesBox, LetterButton, PlanSection } from "@/components/Plan";
import { PolicySection } from "@/components/Policy";
import { VerdictCard, sortFindings } from "@/components/Verdict";
import { INDEPENDENT_NOTICE, RESULT_NOTICE } from "@/i18n";
import { useSession } from "@/state/store";

const today = () => new Date().toLocaleDateString("en-GB"); // DD/MM/YYYY

/**
 * A printable report of the CURRENT in-memory session. There is no stored report: this page renders only while the
 * browser tab still holds this session's result and the id in the address matches the one this tab created. Anyone
 * else (another tab, another person, a reloaded page) gets the expired state, never someone's data.
 */
export default function Results() {
  const { id } = useParams();
  const { state, t } = useSession();
  const { result } = state;
  const valid = !!result && !!state.reportId && id === state.reportId;

  if (!valid || !result) {
    return (
      <Container className="max-w-3xl py-16 md:py-24">
        <ErrorState pageHeading title={t("rp_gone_h")} what={t("rp_gone_what")} why={t("rp_gone_why")} next={t("rp_gone_next")}>
          <Button to="/check-claim">{t("nav_check")}</Button>
          <Button to="/" variant="secondary">
            {t("nav_home")}
          </Button>
        </ErrorState>
      </Container>
    );
  }

  const challengeable = result.findings.some((f) => f.verdict === "CHALLENGEABLE");
  const d = result.deadlines;
  const complaintEntered = !!state.facts.complaint_sent_date?.value;
  return (
    <Container className="max-w-4xl py-10 md:py-14">
      <div className="no-print mb-6 flex flex-wrap items-center justify-between gap-3">
        <p className="m-0 max-w-[54ch] text-ink-soft">{t("rp_session_note")}</p>
        <div className="flex flex-wrap gap-3">
          <Button onClick={() => window.print()}>{t("print")}</Button>
          <Button to="/action-plan" variant="secondary">
            {t("open_plan")}
          </Button>
          <Button to="/check-claim" variant="quiet">
            {t("back_to_result")}
          </Button>
        </div>
      </div>

      <article className="wf">
        <div className="sheet print-sheet">
          <h1 tabIndex={-1} data-page-heading className="m-0 font-display text-h1 font-medium text-ink">
            {t("rp_h")}
          </h1>
          <p className="src">
            {t("rp_printed")}: <time>{today()}</time>
          </p>
          {!result.supported ? <p className="not-rules-check" role="note">{t("not_rules_check")}</p> : null}
          {!result.findings.length && result.supported ? <p>{t("no_find")}</p> : null}
          <div className="findings">
            {sortFindings(result.findings).map((f, i) => (
              <VerdictCard key={`${f.rule_id}-${i}`} f={f} />
            ))}
          </div>
          {result.text ? (
            <section className="block" aria-labelledby="rp-expl">
              <h3 id="rp-expl">{t("expl")}</h3>
              <div className="expl">{result.text}</div>
            </section>
          ) : null}
          {result.checklist ? <ChecklistSection checklist={result.checklist} /> : null}
          {d && (d.available || (d.note && challengeable)) ? <DeadlinesBox d={d} complaintEntered={complaintEntered} /> : null}
          {result.plan ? <PlanSection plan={result.plan} /> : null}
          {state.policy ? <PolicySection policy={state.policy} /> : null}
          {state.readerBackend ? (
            <p className="src">
              {t("backend")}: {state.readerBackend}
            </p>
          ) : null}
          <hr className="stitch" />
          <p className="notice-result">
            {RESULT_NOTICE}
            {state.lang === "hi" ? <span lang="hi"> {t("notice_result_hi")}</span> : null}
          </p>
          <p className="src">{INDEPENDENT_NOTICE}</p>
          {challengeable && d?.available && d.letter_available !== false ? (
            <div className="actions no-print">
              <LetterButton />
            </div>
          ) : null}
        </div>
      </article>
    </Container>
  );
}
