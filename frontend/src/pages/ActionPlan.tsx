import { useEffect, useState, type ReactNode } from "react";
import { Button } from "@/components/ds/Button";
import { EmptyState } from "@/components/ds/EmptyState";
import { PageHeader } from "@/components/ds/PageHeader";
import { QuoteSlip } from "@/components/ds/QuoteSlip";
import { ReportSection } from "@/components/ds/ReportSection";
import { StatusBadge } from "@/components/ds/StatusBadge";
import { Container } from "@/components/ds/Section";
import { DeadlinesBox, LetterButton, PlanSection } from "@/components/Plan";
import { sortFindings } from "@/components/Verdict";
import { GROUND_LABEL, PRODUCT_LABEL, REJECTION_GROUNDS, RESULT_NOTICE, pick, type Key, type RejectionGround } from "@/i18n";
import { ART } from "@/content/art";
import { cn } from "@/lib/utils";
import { useSession } from "@/state/store";

export interface PlanTask {
  id: string;
  group: "docs" | "steps";
  text: string;
}

/** The checklist, derived only from what the API returned: documents to request, and the plan's own steps. */
export function buildTasks(result: NonNullable<ReturnType<typeof useSession>["state"]["result"]>, lang: "en" | "hi"): PlanTask[] {
  const tasks: PlanTask[] = [];
  result.checklist?.items.forEach((it, i) => {
    const text = pick(it, lang);
    if (text) tasks.push({ id: `doc-${i}`, group: "docs", text });
  });
  result.plan?.steps.forEach((step) =>
    step.items.forEach((it, i) => {
      const text = it.text ? pick(it.text, lang) : "";
      if (text) tasks.push({ id: `step-${step.id}-${i}`, group: "steps", text });
    }),
  );
  return tasks;
}

function Tick({ task }: { task: PlanTask }) {
  const { state, actions } = useSession();
  const on = !!state.checkedItems[task.id];
  return (
    <li>
      <label className="flex min-h-11 cursor-pointer items-start gap-3 py-1.5">
        <input type="checkbox" checked={on} onChange={() => actions.toggleChecked(task.id)} className="mt-0.5 size-6 shrink-0 accent-ink" />
        <span className={cn(on && "text-ink-soft line-through decoration-1")}>{task.text}</span>
      </label>
    </li>
  );
}

export default function ActionPlan() {
  const { state, t } = useSession();
  const { result, lang } = state;

  if (!result) {
    return (
      <>
        <PageHeader title={t("ap_h")} lead={t("ap_lead")} />
        <Container className="py-12 md:py-16">
          <EmptyState title={t("ap_empty_h")} art={<img src={ART.folder} alt="" aria-hidden="true" width={200} height={200} className="w-40 rounded-ctl border border-line" />}>
            <p className="m-0">{t("ap_empty_p")}</p>
            <p className="m-0">{t("ap_empty_next")}</p>
            <div className="pt-2">
              <Button to="/check-claim">{t("nav_check")}</Button>
            </div>
          </EmptyState>
        </Container>
      </>
    );
  }

  const g = state.facts.rejection_ground;
  const gValue = typeof g?.value === "string" ? g.value : "";
  const reason = (REJECTION_GROUNDS as readonly string[]).includes(gValue) ? GROUND_LABEL[lang][gValue as RejectionGround] : gValue;
  const product = (PRODUCT_LABEL[lang] as Record<string, string>)[result.productLine] ?? result.productLine;
  const flagged = sortFindings(result.findings).filter((f) => f.verdict !== "CONSISTENT");
  const raise = flagged.filter((f) => f.verdict === "CHALLENGEABLE");
  const challengeable = raise.length > 0;
  const tasks = buildTasks(result, lang);
  const done = tasks.filter((x) => state.checkedItems[x.id]).length;
  const docs = tasks.filter((x) => x.group === "docs");
  const steps = tasks.filter((x) => x.group === "steps");
  const complaintEntered = !!state.facts.complaint_sent_date?.value;
  const page = (n: number | null) => (n != null ? ` (${t("page")} ${n})` : "");

  const sections = [
    { id: "ap-what", label: t("ap_what_h") },
    ...(result.supported ? [{ id: "ap-issues", label: t("ap_issues_h") }] : []),
    { id: "ap-docs", label: t("ap_docs_h") },
    { id: "ap-raise", label: t("ap_raise_h") },
    { id: "ap-esc", label: t("ap_esc_h") },
    { id: "ap-check", label: t("ap_check_h") },
    { id: "ap-resources", label: t("ap_resources_h") },
    { id: "ap-not", label: t("ap_not_h") },
  ];
  const current = useCurrentSection(sections.map((s) => s.id));

  const finding = (f: (typeof flagged)[number], i: number): ReactNode => {
    const q = lang === "hi" ? f.question_hi || f.question_en : f.question_en;
    const a = lang === "hi" ? f.action_hi || f.action_en : f.action_en;
    return (
      <li key={`${f.rule_id}-${i}`} className="space-y-3 border-t border-line pt-5 first:border-t-0 first:pt-0">
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge verdict={f.verdict} />
          <span className="font-semibold text-ink">{t(f.verdict as Key)}</span>
        </div>
        {f.verdict === "NEED_INFO" && q ? (
          <p className="m-0">
            <strong>{t("ask")}: </strong>
            {q}
          </p>
        ) : null}
        {a ? (
          <p className="m-0">
            <strong>{t("act")}: </strong>
            {a}
          </p>
        ) : null}
        <QuoteSlip source={`${t("rule")}${page(f.page_no)}`}>{f.rule_quote}</QuoteSlip>
      </li>
    );
  };

  return (
    <>
      <PageHeader title={t("ap_h")} lead={t("ap_lead")} />
      <Container className="plan-grid max-w-5xl py-10 md:py-14">
        <p className="m-0 border border-line-strong bg-paper px-4 py-3 font-semibold text-ink" role="note">
          {RESULT_NOTICE}
          {lang === "hi" ? <span lang="hi"> {t("notice_result_hi")}</span> : null}
        </p>

        <nav className="plan-rail no-print" aria-label={t("rail_sections")}>
          <ul>
            {sections.map((s) => (
              <li key={s.id}>
                <a href={`#${s.id}`} aria-current={current === s.id ? "true" : undefined}>
                  {s.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <ReportSection id="ap-what" title={t("ap_what_h")}>
          <dl className="m-0 grid gap-x-8 gap-y-3 sm:grid-cols-[12rem_1fr]">
            <dt className="font-semibold text-ink">{t("ap_type")}</dt>
            <dd className="m-0">{product}</dd>
            <dt className="font-semibold text-ink">{t("ap_reason")}</dt>
            <dd className="m-0">{reason || t("ap_reason_none")}</dd>
          </dl>
          {g?.quote ? <QuoteSlip source={`${t("src")}${page(g.page_no)}`}>{g.quote}</QuoteSlip> : null}
          {!result.supported ? <p className="not-rules-check m-0 border-2 border-ink bg-slip px-4 py-3 font-semibold" role="note">{t("not_rules_check")}</p> : null}
        </ReportSection>

        {result.supported ? (
          <ReportSection id="ap-issues" title={t("ap_issues_h")}>
            {flagged.length ? <ul className="m-0 list-none space-y-5 p-0">{flagged.map(finding)}</ul> : <p className="m-0">{result.findings.length ? t("ap_none_flagged") : t("no_find")}</p>}
          </ReportSection>
        ) : null}

        <ReportSection id="ap-docs" title={t("ap_docs_h")}>
          {docs.length ? <ul className="m-0 list-disc space-y-1 pl-5">{docs.map((d) => <li key={d.id}>{d.text}</li>)}</ul> : <p className="m-0">{t("ap_docs_none")}</p>}
        </ReportSection>

        <ReportSection id="ap-raise" title={t("ap_raise_h")}>
          {challengeable ? (
            <ul className="m-0 list-disc space-y-2 pl-5">
              {raise.map((f, i) => (
                <li key={`${f.rule_id}-${i}`}>{(lang === "hi" ? f.action_hi || f.action_en : f.action_en) || t(f.verdict as Key)}</li>
              ))}
            </ul>
          ) : (
            <p className="m-0">{t("ap_raise_none")}</p>
          )}
        </ReportSection>

        <ReportSection id="ap-esc" title={t("ap_esc_h")}>
          <div className="wf">
            {result.deadlines && (result.deadlines.available || result.deadlines.note) ? <DeadlinesBox d={result.deadlines} complaintEntered={complaintEntered} /> : null}
            {result.plan ? <PlanSection plan={result.plan} /> : null}
          </div>
        </ReportSection>

        <ReportSection id="ap-check" title={t("ap_check_h")}>
          {tasks.length ? (
            <>
              <p role="status" aria-live="polite" className="m-0 text-ink-soft">
                {done} / {tasks.length} {t("ap_done")}
              </p>
              {docs.length ? (
                <fieldset className="m-0 min-w-0 border-0 p-0">
                  <legend className="mb-1 p-0 font-semibold text-ink">{t("ap_docs_h")}</legend>
                  <ul className="m-0 list-none p-0">{docs.map((d) => <Tick key={d.id} task={d} />)}</ul>
                </fieldset>
              ) : null}
              {steps.length ? (
                <fieldset className="m-0 min-w-0 border-0 p-0">
                  <legend className="mb-1 p-0 font-semibold text-ink">{t("ap_steps_h")}</legend>
                  <ul className="m-0 list-none p-0">{steps.map((d) => <Tick key={d.id} task={d} />)}</ul>
                </fieldset>
              ) : null}
              <p className="m-0 text-control text-ink-soft">{t("ap_session_note")}</p>
            </>
          ) : (
            <p className="m-0">{t("ap_check_none")}</p>
          )}
        </ReportSection>

        <ReportSection id="ap-resources" title={t("ap_resources_h")}>
          <p className="m-0">{t("ap_resources_p")}</p>
        </ReportSection>

        <ReportSection id="ap-not" title={t("ap_not_h")}>
          <p className="m-0">{t("ap_not_p")}</p>
        </ReportSection>

        <div className="no-print flex flex-wrap gap-3 border-t border-line pt-8">
          <Button variant="secondary" onClick={() => window.print()}>
            {t("ap_print")}
          </Button>
          {state.reportId ? (
            <Button to={`/results/${state.reportId}`} variant="secondary">
              {t("open_report")}
            </Button>
          ) : null}
          <Button to="/check-claim" variant="quiet">
            {t("back_to_result")}
          </Button>
          {challengeable && result.deadlines?.available && result.deadlines.letter_available !== false ? (
            <div className="wf">
              <LetterButton />
            </div>
          ) : null}
        </div>
      </Container>
    </>
  );
}

/** Which section is being read: the last one whose top has passed the band just under the navbar. */
function useCurrentSection(ids: string[]) {
  const [current, setCurrent] = useState(ids[0] ?? "");
  const key = ids.join(",");
  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) setCurrent(e.target.id);
      },
      { rootMargin: "-20% 0px -65% 0px", threshold: 0 },
    );
    for (const id of key.split(",")) {
      const el = document.getElementById(id);
      if (el) io.observe(el);
    }
    return () => io.disconnect();
  }, [key]);
  return current;
}
