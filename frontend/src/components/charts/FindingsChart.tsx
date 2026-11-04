import { motion, useReducedMotion } from "motion/react";
import type { Finding, Verdict } from "@/api";
import { GROUND_LABEL, type Key } from "@/i18n";
import type { RejectionGround } from "@/i18n/labels";
import { EASE } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { useSession } from "@/state/store";
import { WINNERS, fill, useSimilarCases, type Winner } from "./RealCases";

/*
 * The result in one picture, in the simplest honest form: two bars of counts, never a probability.
 *   1. What the rules say: every rule the claim was checked against, split by verdict (counted from the findings).
 *   2. What happened to others: reviewed real judgments with the same stated reason, split by who won (counted from
 *      the case base). It shows what happened to others; it does not predict this claim, and says so.
 * Small n, so segmented bars with the count written on each part (no axis to decode, never colour alone: every
 * segment carries its word or count, and the whole bar has a sentence for screen readers).
 */

const ORDER: Verdict[] = ["CHALLENGEABLE", "NEED_INFO", "CONSISTENT"];
const VERDICT_SEG: Record<Verdict, string> = {
  CHALLENGEABLE: "bg-terracotta-wash text-terracotta-ink border-terracotta",
  NEED_INFO: "bg-amber-wash text-amber-ink border-amber-ink/50",
  CONSISTENT: "bg-sage-wash text-sage-ink border-sage",
};
const WIN_SEG: Record<Winner, string> = {
  policyholder: "bg-ink text-on-ink border-ink",
  insurer: "bg-paper text-ink border-ink",
  unknown: "bg-ivory text-ink-soft border-line-strong",
};

function Bar({ parts, label }: { parts: Array<{ id: string; n: number; text: string; cls: string }>; label: string }) {
  const reduce = useReducedMotion();
  const shown = parts.filter((p) => p.n > 0);
  return (
    <motion.div
      role="img"
      aria-label={label}
      className="fx-bar"
      style={{ originX: 0 }}
      {...(reduce ? {} : { initial: { scaleX: 0 }, whileInView: { scaleX: 1 }, viewport: { once: true }, transition: { duration: 0.8, ease: EASE } })}
    >
      {shown.map((p) => (
        <span key={p.id} data-part={p.id} className={cn("fx-seg", p.cls)} style={{ flexGrow: p.n }}>
          <strong>{p.n}</strong>
          <span className="fx-seg-word">{p.text}</span>
        </span>
      ))}
    </motion.div>
  );
}

export function FindingsChart({ findings, ground }: { findings: Finding[]; ground: RejectionGround | null }) {
  const { state, t } = useSession();
  const cases = useSimilarCases(ground);
  const total = findings.length;
  if (!total) return null;

  const count = (v: Verdict) => findings.filter((f) => f.verdict === v).length;
  const rules = ORDER.map((v) => ({ id: v, n: count(v), text: t(`vw_${v}` as Key), cls: VERDICT_SEG[v] }));
  const won = cases.counts.policyholder;
  const seen = cases.cases.length;
  const groundLabel = ground ? ((GROUND_LABEL[state.lang] as Record<string, string>)[ground] ?? ground) : "";

  return (
    <section className="block fx-chart" aria-labelledby="fx-h">
      <h3 id="fx-h">{t("fx_h" as Key)}</h3>

      <div className="fx-row">
        <p className="fx-title">{t("fx_rules" as Key)}</p>
        <p className="fx-line">
          {fill(t("fx_rules_line" as Key), { total, c: count("CHALLENGEABLE"), n: count("NEED_INFO"), k: count("CONSISTENT") })}
        </p>
        <Bar parts={rules} label={rules.map((r) => `${r.text}: ${r.n}`).join(", ")} />
      </div>

      {seen ? (
        <div className="fx-row">
          <p className="fx-title">{fill(t("fx_cases" as Key), { ground: groundLabel })}</p>
          <p className="fx-line">{fill(t("rc_won_line"), { won, total: seen })}</p>
          <Bar
            parts={WINNERS.map((w) => ({ id: w, n: cases.counts[w], text: t(`won_${w}` as Key), cls: WIN_SEG[w] }))}
            label={WINNERS.filter((w) => cases.counts[w]).map((w) => `${t(`won_${w}` as Key)}: ${cases.counts[w]}`).join(", ")}
          />
          <p className="fx-more">
            <a href="#real-cases">{t("fx_cases_link" as Key)}</a>
          </p>
        </div>
      ) : null}

      <p className="fx-note">{t("fx_note" as Key)}</p>
    </section>
  );
}
