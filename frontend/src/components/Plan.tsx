import { useState } from "react";
import type { Deadlines, DeadlineSource, Plan, PlanItem, RequestChecklist as Checklist } from "../api";
import { pick } from "../i18n";
import { rowOrder } from "../lib/motion";
import { useSession } from "../state/store";
import { ErrorBox } from "./ErrorBox";
import { IconDownload } from "./icons";
import { Quote, RuleChip } from "./evidence";
import { RouteMap, stepAnchor } from "./plan/RouteMap";
import { DeadlineTimeline } from "./charts/DeadlineTimeline";

/** The grievance-letter download. A 409 (no challengeable finding, rule card missing) is shown, not navigated to. */
export function LetterButton({ className = "" }: { className?: string }) {
  const { state, actions, t } = useSession();
  const [err, setErr] = useState<string | null>(null);
  const busy = state.busy === "letter";
  return (
    <>
      <button
        type="button"
        className={`with-icon ${className}`}
        disabled={busy}
        onClick={async () => {
          setErr(null);
          const out = await actions.downloadLetter();
          if (!out.ok) setErr(out.error.kind === "expired" ? t("expired") : out.error.message);
        }}
      >
        <IconDownload />
        <span>{t("letter")}</span>
      </button>
      {err ? <ErrorBox message={err} /> : null}
    </>
  );
}

export function PlanItemView({ item }: { item: PlanItem }) {
  const { state, t } = useSession();
  const lang = state.lang;
  const text = item.text ? pick(item.text, lang) : "";
  return (
    <li>
      {item.rule_id ? <RuleChip id={item.rule_id} /> : null}
      {text ? <span className="plan-text"> {text}</span> : null}
      {item.date ? (
        <div className="plan-date">
          <strong>{item.date_label ? `${pick(item.date_label, lang)}: ` : ""}</strong>
          <time dateTime={item.date.iso}>{item.date.display}</time>
        </div>
      ) : null}
      {item.source_label ? (
        <p className="src">{pick(item.source_label, lang)}</p>
      ) : item.quote ? (
        <Quote
          source={`${t("rule")}${item.page_no != null ? ` (${t("page")} ${item.page_no})` : ""}${
            item.source_title ? ` · ${t("src")}: ${item.source_title}` : ""
          }`}
        >
          {item.quote}
        </Quote>
      ) : null}
      {item.link === "letter" && state.sid ? (
        <div className="plan-link">
          <LetterButton />
        </div>
      ) : null}
    </li>
  );
}

export function PlanSection({ plan }: { plan: Plan }) {
  const { state, t } = useSession();
  const general = plan.kind === "general";
  return (
    <section className="block" aria-labelledby="plan-h" id="plan">
      <h3 id="plan-h">{general ? t("plan_gen_h") : t("plan_h")}</h3>
      {general ? <p className="lede">{pick(plan.title, state.lang)}</p> : null}
      {plan.steps.length > 1 ? <RouteMap plan={plan} /> : null}
      <ol className="plan plan-rail">
        {plan.steps.map((s, n) => (
          <li key={s.id} id={stepAnchor(s.id)} data-n={n + 1}>
            <h4 tabIndex={-1}>{pick(s.title, state.lang)}</h4>
            <ul>
              {s.items.map((it, i) => (
                <PlanItemView key={`${s.id}-${i}`} item={it} />
              ))}
            </ul>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function ChecklistSection({ checklist }: { checklist: Checklist }) {
  const { state } = useSession();
  return (
    <section className="block" aria-labelledby="ck-h" id="checklist">
      <h3 id="ck-h">{pick(checklist.title, state.lang)}</h3>
      <p>{pick(checklist.intro, state.lang)}</p>
      <ul className="checklist">
        {checklist.items.map((i, n) => (
          <li key={n} style={rowOrder(n)}>{pick(i, state.lang)}</li>
        ))}
      </ul>
    </section>
  );
}

type DlKey = "insurer_reply_by" | "ombudsman_earliest" | "ombudsman_latest";
const DL_LABEL = { insurer_reply_by: "d1", ombudsman_earliest: "d2", ombudsman_latest: "d3" } as const;

/**
 * Deadlines. Dates are shown ONLY when the user entered the date they sent their complaint.
 * The API counts from today's date when none was entered; we never show such a date, because it is an assumption.
 */
export function DeadlinesBox({ d, complaintEntered }: { d: Deadlines; complaintEntered: boolean }) {
  const { state, t } = useSession();
  const lang = state.lang;
  const showDates = d.available && complaintEntered && d.letter_available !== false;
  const keys: DlKey[] = ["insurer_reply_by", "ombudsman_earliest", "ombudsman_latest"];
  const src = (k: DlKey): DeadlineSource | undefined => d.sources?.[k];
  return (
    <section className="block" aria-labelledby="dl-h" id="deadlines">
      <h3 id="dl-h">{t("dl")}</h3>
      {showDates ? <DeadlineTimeline d={d} /> : null}
      {showDates ? (
        <ul className="deadlines">
          {keys.map((k, n) => {
            const date = d[k];
            if (!date) return null;
            const s = src(k);
            return (
              <li key={k} style={rowOrder(n)}>
                <span className="dl-label">{t(DL_LABEL[k])}: </span>
                <time dateTime={date.iso}>{date.display}</time>
                {s?.label ? (
                  <p className="src">{pick(s.label, lang)}</p>
                ) : s?.quote ? (
                  <Quote
                    source={`${t("rule")}${s.page_no != null ? ` (${t("page")} ${s.page_no})` : ""}${
                      s.source_id ? ` · ${t("src")}: ${s.source_id}` : ""
                    }`}
                  >
                    {s.quote}
                  </Quote>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="need-date">{d.available ? t("dl_need_date") : d.note || ""}</p>
      )}
      {showDates && d.note ? <p className="src">{d.note}</p> : null}
      {d.rule_quote ? (
        <div className="grievance">
          {d.rule_id ? <RuleChip id={d.rule_id} /> : null}
          <Quote
            source={`${t("rule")}${d.page_no != null ? ` (${t("page")} ${d.page_no})` : ""}${
              d.source_sha256 ? ` · ${t("src")}: ${d.source_sha256.slice(0, 12)}` : ""
            }`}
          >
            {d.rule_quote}
          </Quote>
        </div>
      ) : null}
    </section>
  );
}
