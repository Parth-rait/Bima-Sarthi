import { useState } from "react";
import { Button } from "../components/ds/Button";
import { Modal } from "../components/ds/Modal";
import { ErrorBox } from "../components/ErrorBox";
import { IconPrint, IconTrash } from "../components/icons";
import { FindingsChart } from "../components/charts/FindingsChart";
import { RealCases } from "../components/charts/RealCases";
import { ChecklistSection, DeadlinesBox, LetterButton, PlanSection } from "../components/Plan";
import { PolicySection } from "../components/Policy";
import { ResultSummary } from "../components/Summary";
import { VerdictCard, sortFindings } from "../components/Verdict";
import { Field, Stitch } from "../components/evidence";
import { describeError, type ViewError } from "../lib/errors";
import type { Key } from "../i18n";
import { REJECTION_GROUNDS, type RejectionGround } from "../i18n/labels";
import { labelOf } from "../lib/facts";
import { useSession } from "../state/store";

/** Complaint-sent and insurer-reply dates. Re-runs the check so deadlines and the plan use them. */
function ComplaintDates() {
  const { state, actions, t } = useSession();
  const existing = state.facts.complaint_sent_date?.value;
  const [sent, setSent] = useState(typeof existing === "string" ? existing : "");
  const [reply, setReply] = useState("");
  const [err, setErr] = useState<ViewError | null>(null);
  const [saved, setSaved] = useState(false);
  const busy = state.busy === "facts" || state.busy === "check" || state.busy === "explain";
  const label = (k: string) => labelOf(k, state.lang, { facts: state.facts, labels: state.labels });

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setErr(null);
    setSaved(false);
    const s = sent.trim();
    const r = reply.trim();
    if (!s && !r) return;
    const out = await actions.saveAndCheck({
      facts: s ? { complaint_sent_date: { value: s } } : {},
      ...(r ? { insurer_reply_date: r } : {}),
    });
    if (out.ok) setSaved(true);
    else setErr(describeError(out.error, t, label));
  };
  return (
    <form className="block" aria-labelledby="cd-h" onSubmit={submit} noValidate>
      <h3 id="cd-h">{t("cd_h")}</h3>
      <p className="hint">{t("cd_p")}</p>
      <div className="grid2">
        <Field label={t("sentdate")} error={err?.fieldErrors.complaint_sent_date}>
          {(p) => (
            <input {...p} type="text" inputMode="numeric" placeholder="DD/MM/YYYY" value={sent} onChange={(e) => setSent(e.target.value)} />
          )}
        </Field>
        <Field label={t("replydate")} error={err?.fieldErrors.insurer_reply_date}>
          {(p) => (
            <input {...p} type="text" inputMode="numeric" placeholder="DD/MM/YYYY" value={reply} onChange={(e) => setReply(e.target.value)} />
          )}
        </Field>
      </div>
      {err ? <ErrorBox message={err.message} items={err.items} /> : null}
      <p role="status" className="status">
        {busy ? t("saving") : saved ? t("cd_saved") : ""}
      </p>
      <div className="actions">
        <button type="submit" className="secondary" disabled={busy}>
          {t("cd_save")}
        </button>
      </div>
    </form>
  );
}

export function ResultScreen() {
  const { state, actions, t } = useSession();
  const { result } = state;
  if (!result) return null;
  const challengeable = result.findings.some((f) => f.verdict === "CHALLENGEABLE");
  const d = result.deadlines;
  const complaintEntered = !!state.facts.complaint_sent_date?.value;
  const general = !result.supported;
  const thinking = state.busy === "explain";
  const [confirmDelete, setConfirmDelete] = useState(false);
  const gv = state.facts.rejection_ground?.value;
  const groundKey = typeof gv === "string" && (REJECTION_GROUNDS as readonly string[]).includes(gv) ? (gv as RejectionGround) : null;

  return (
    <section aria-labelledby="h-result" className="screen result">
      <h2 id="h-result" tabIndex={-1} data-screen-heading>
        {t("r_h")}
      </h2>

      {result.findings.length ? <ResultSummary findings={result.findings} /> : null}

      {/* one block, not a grid row each: the summary has to be able to stick the length of the report */}
      <div className="report">
      {general ? (
        <p className="not-rules-check" role="note">
          {t("not_rules_check")}
        </p>
      ) : null}
      {/* the result in one picture: rules by verdict, and real cases with the same reason by who won (counts only) */}
      <FindingsChart findings={result.findings} ground={groundKey} />

      {!result.findings.length && !general ? <p>{t("no_find")}</p> : null}

      {result.findings.length ? (
        <div className="findings">
          {sortFindings(result.findings).map((f, i) => (
            <VerdictCard key={`${f.rule_id}-${i}`} f={f} i={i} />
          ))}
        </div>
      ) : null}

      {result.text ? (
        <section className="block" aria-labelledby="h-expl">
          <h3 id="h-expl">{t("expl")}</h3>
          <div className="expl">{result.text}</div>
        </section>
      ) : null}
      <p role="status" className="status">
        {thinking ? t("checking") : ""}
        {state.busy && state.slow ? ` ${t("slow")}` : ""}
      </p>
      {result.explainFailed ? <p className="muted">{t("explain_missing")}</p> : null}

      {result.checklist ? <ChecklistSection checklist={result.checklist} /> : null}
      {state.readerBackend ? (
        <p className="src">
          {t("backend")}: {state.readerBackend}
        </p>
      ) : null}

      {d && (d.available || (d.note && challengeable)) ? <DeadlinesBox d={d} complaintEntered={complaintEntered} /> : null}
      {result.plan ? <PlanSection plan={result.plan} /> : null}
      {result.findings.length && groundKey ? <RealCases ground={groundKey} /> : null}
      {state.policy ? <PolicySection policy={state.policy} /> : null}

      <ComplaintDates />

      <Stitch />
      <div className="actions result-actions">
        {/* trace back: the answers are kept, so changing one and pressing the check again replaces this result */}
        <button type="button" className="secondary" onClick={() => actions.setStep(2)} disabled={!!state.busy}>
          {t("back_answers" as Key)}
        </button>
        {challengeable && d?.available && d.letter_available !== false ? <LetterButton /> : null}
        {state.helper ? (
          <button type="button" className="secondary with-icon" onClick={() => window.print()}>
            <IconPrint />
            <span>{t("print")}</span>
          </button>
        ) : null}
        <button type="button" className="danger with-icon" onClick={() => setConfirmDelete(true)} disabled={state.busy === "delete"}>
          <IconTrash />
          <span>{t("del")}</span>
        </button>
      </div>
      <div className="actions result-links">
        <Button to="/action-plan" variant="secondary">
          {t("open_plan")}
        </Button>
        {state.reportId ? (
          <Button to={`/results/${state.reportId}`} variant="secondary">
            {t("open_report")}
          </Button>
        ) : null}
      </div>
      </div>
      <Modal
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title={t("del_confirm_h")}
        description={t("del_confirm_p")}
        closeLabel={t("close")}
      >
        <Button
          variant="danger"
          onClick={() => {
            setConfirmDelete(false);
            void actions.deleteData();
          }}
        >
          {t("del_confirm_yes")}
        </Button>
        <Button variant="secondary" data-autofocus onClick={() => setConfirmDelete(false)}>
          {t("del_confirm_no")}
        </Button>
      </Modal>
    </section>
  );
}
