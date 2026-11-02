import type { Finding } from "../api";
import { showVal, labelOf } from "../lib/facts";
import { useSession } from "../state/store";
import { Quote, RuleChip, Stamp } from "./evidence";
import type { Key } from "../i18n";

const ORDER = { CHALLENGEABLE: 0, NEED_INFO: 1, CONSISTENT: 2 } as const;
export const sortFindings = (fs: Finding[]): Finding[] => [...fs].sort((a, b) => ORDER[a.verdict] - ORDER[b.verdict]);

/**
 * One finding. The verdict is carried three ways at once: a word, a shape (triangle / circle / square),
 * and the plain sentence. Colour only reinforces. The rule id appears only as a small "Rule reference" chip:
 * the API provides no plain-language rule title, and we do not invent one.
 */
export function VerdictCard({ f }: { f: Finding }) {
  const { state, t } = useSession();
  const { lang } = state;
  const q = lang === "hi" ? f.question_hi || f.question_en : f.question_en;
  const a = lang === "hi" ? f.action_hi || f.action_en : f.action_en;
  const label = (k: string) => labelOf(k, lang, { facts: state.facts, labels: state.labels, policy: state.policy });
  const yn = (b: boolean) => (b ? t("yes") : t("no"));
  const used = Object.entries(f.facts_used || {}).filter(([, v]) => v && v.quote);
  const page = f.page_no != null ? ` (${t("page")} ${f.page_no})` : "";
  return (
    <article className={`finding finding-${f.verdict}`} data-verdict={f.verdict} data-rule={f.rule_id}>
      <header className="finding-head">
        <Stamp verdict={f.verdict} />
        <RuleChip id={f.rule_id} />
      </header>
      <h3>{t(f.verdict as Key)}</h3>
      <Quote source={`${t("rule")}${page}`}>{f.rule_quote}</Quote>
      {used.length ? (
        <div className="facts-used">
          <p className="label">{t("fq")}</p>
          <ul>
            {used.map(([k, v]) => (
              <li key={k}>
                <Quote source={`${t("page")} ${v.page_no ?? "-"}`}>
                  <strong>{label(k)}: </strong>
                  {showVal(v.value, k, lang, yn, label)}
                  {" — “"}
                  {v.quote}
                  {"”"}
                </Quote>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {f.verdict === "NEED_INFO" && q ? (
        <p>
          <strong>{t("ask")}: </strong>
          {q}
        </p>
      ) : null}
      {f.verdict !== "CONSISTENT" && a ? (
        <p>
          <strong>{t("act")}: </strong>
          {a}
        </p>
      ) : null}
    </article>
  );
}
