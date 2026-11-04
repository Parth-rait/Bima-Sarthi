import { useEffect, useState, type KeyboardEvent } from "react";
import { motion, useReducedMotion } from "motion/react";
import type { Plan, PlanStep } from "@/api";
import { pick, type Key } from "@/i18n";
import { fill } from "@/components/charts/RealCases";
import { AnimatedNumber } from "@/components/ui/motion-primitives";
import { ShaderRings } from "@/components/ui/shader-rings";
import { EASE } from "@/lib/motion";
import { useSession } from "@/state/store";

/*
 * The plan as a route you can see: every step a stop, the two "only if" turns drawn as decisions with the way out
 * written on them. Interactive both ways: pressing a stop scrolls to that step's detail (rules and quotes) below,
 * and scrolling the detail moves the marker on the map. Nothing here is new information: the stops are the API's
 * plan steps, the decisions are the conditions already written in those steps' titles, the counts are counted.
 */

type Stop = { kind: "step"; step: PlanStep; n: number } | { kind: "turn"; id: string; q: Key; yes: Key };

/** A decision sits in front of the steps whose title is itself a condition ("If the insurer ... does not reply"). */
const TURN: Record<string, { q: Key; yes: Key; label: Key }> = {
  ombudsman: { q: "pf_q_reply" as Key, yes: "pf_yes_settled" as Key, label: "pf_omb" as Key },
  commission: { q: "pf_q_limit" as Key, yes: "pf_yes_commission" as Key, label: "pf_commission" as Key },
};

export const stepAnchor = (id: string) => `plan-step-${id}`;

export function stops(plan: Plan): Stop[] {
  const out: Stop[] = [];
  plan.steps.forEach((step, i) => {
    const turn = TURN[step.id];
    if (turn) out.push({ kind: "turn", id: `turn-${step.id}`, q: turn.q, yes: turn.yes });
    out.push({ kind: "step", step, n: i + 1 });
  });
  return out;
}

const cited = (s: PlanStep) => s.items.filter((i) => i.rule_id || i.quote).length;
const dated = (s: PlanStep) => s.items.find((i) => i.date)?.date ?? null;

/** Follows which step's detail is on screen, so the map's marker can travel with the reader. */
function useActiveStep(ids: string[]) {
  const [active, setActive] = useState(ids[0] ?? "");
  useEffect(() => {
    const els = ids.map((id) => document.getElementById(stepAnchor(id))).filter((e): e is HTMLElement => !!e);
    if (!els.length) return;
    const io = new IntersectionObserver(
      (entries) => {
        const top = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (top) setActive(top.target.id.replace("plan-step-", ""));
      },
      { rootMargin: "-30% 0px -55% 0px" },
    );
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  }, [ids.join("|")]); // eslint-disable-line react-hooks/exhaustive-deps
  return [active, setActive] as const;
}

export function RouteMap({ plan }: { plan: Plan }) {
  const { state, t } = useSession();
  const lang = state.lang;
  const reduce = useReducedMotion();
  const all = stops(plan);
  const ids = plan.steps.map((s) => s.id);
  const [active, setActive] = useActiveStep(ids);
  const turns = all.filter((s) => s.kind === "turn").length;
  const rules = plan.steps.reduce((n, s) => n + cited(s), 0);

  const go = (id: string) => {
    setActive(id);
    const el = document.getElementById(stepAnchor(id));
    el?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    el?.querySelector<HTMLElement>("h4")?.focus({ preventScroll: true });
  };
  // arrow keys walk the stops, like a toolbar (one tab stop for the whole map)
  const onKey = (e: KeyboardEvent<HTMLOListElement>) => {
    if (!["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
    e.preventDefault();
    const i = Math.max(0, ids.indexOf(active));
    const next = e.key === "Home" ? 0 : e.key === "End" ? ids.length - 1 : e.key === "ArrowRight" || e.key === "ArrowDown" ? Math.min(ids.length - 1, i + 1) : Math.max(0, i - 1);
    setActive(ids[next]);
    e.currentTarget.querySelector<HTMLButtonElement>(`[data-stop="${ids[next]}"]`)?.focus();
  };

  const label = (s: PlanStep) => {
    const turn = TURN[s.id];
    if (turn) return t(turn.label);
    return pick(s.title, lang);
  };

  return (
    <div className="route-plate">
      <span className="route-rings" aria-hidden="true">
        <ShaderRings />
      </span>
      <div className="route-head">
        <p className="route-sum">
          <span className="route-stat">
            <AnimatedNumber value={plan.steps.length} /> {t("pf_steps" as Key)}
          </span>
          <span className="route-stat">
            <AnimatedNumber value={turns} /> {t("pf_turns" as Key)}
          </span>
          <span className="route-stat">
            <AnimatedNumber value={rules} /> {t("pf_rules" as Key)}
          </span>
        </p>
        <p className="route-hint">{t("pf_hint" as Key)}</p>
      </div>
      <ol className="route-map" aria-label={t("pf_map" as Key)} onKeyDown={onKey}>
        {all.map((s, i) => {
          const delay = reduce ? 0 : 0.06 * i;
          const enter = reduce
            ? {}
            : { initial: { opacity: 0, y: 14 }, whileInView: { opacity: 1, y: 0 }, viewport: { once: true, margin: "-10% 0px" }, transition: { duration: 0.5, ease: EASE, delay } };
          if (s.kind === "turn") {
            return (
              <motion.li key={s.id} className="route-turn" {...enter}>
                <span className="route-link" aria-hidden="true" />
                <span className="route-decision">
                  <span className="route-diamond" aria-hidden="true">
                    <span>?</span>
                  </span>
                  <span className="route-q">{t(s.q)}</span>
                  <span className="route-branch">
                    <span className="route-yes">{t("yes")}</span> {t(s.yes)}
                  </span>
                  <span className="route-no">
                    {t("no")} <span aria-hidden="true">→</span>
                  </span>
                </span>
              </motion.li>
            );
          }
          const on = active === s.step.id;
          const date = dated(s.step);
          const c = cited(s.step);
          return (
            <motion.li key={s.step.id} className="route-stop" data-on={on || undefined} {...enter}>
              {i > 0 ? <span className="route-link" aria-hidden="true" /> : null}
              <button
                type="button"
                data-stop={s.step.id}
                className="route-node"
                aria-current={on ? "step" : undefined}
                aria-controls={stepAnchor(s.step.id)}
                tabIndex={on ? 0 : -1}
                onClick={() => go(s.step.id)}
              >
                {on ? <motion.span layoutId={reduce ? undefined : "route-on"} className="route-on" transition={{ type: "spring", stiffness: 380, damping: 32 }} /> : null}
                <span className="route-n">{s.n}</span>
                <span className="route-title">{label(s.step)}</span>
                <span className="route-chips">
                  {c ? <span className="route-chip">{fill(t("pf_cited" as Key), { n: c })}</span> : null}
                  {date ? <time className="route-chip" dateTime={date.iso}>{date.display}</time> : null}
                </span>
              </button>
            </motion.li>
          );
        })}
      </ol>
    </div>
  );
}
