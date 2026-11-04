import { motion, useReducedMotion } from "motion/react";
import type { Deadlines } from "@/api";
import type { Key } from "@/i18n";
import { EASE } from "@/lib/motion";
import { useSession } from "@/state/store";
import { fill } from "./RealCases";

const DAY = 86_400_000;
const at = (iso: string) => Date.parse(`${iso}T00:00:00Z`);

interface Row {
  id: "reply" | "ombudsman";
  label: string;
  start: { iso: string; display: string };
  end: { iso: string; display: string };
}

/** Whole days from `todayIso` to `iso` (negative once it has passed). */
export const daysUntil = (iso: string, todayIso: string) => Math.round((at(iso) - at(todayIso)) / DAY);

const localToday = () => {
  const n = new Date();
  return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, "0")}-${String(n.getDate()).padStart(2, "0")}`;
};

/**
 * The two deadline windows on one shared date scale, today marked, every date written on the picture (no axis to
 * decode). Restored from the 4 Nov iteration, now drawn in: each window grows from its start date, and today's
 * marker drops in last. Drawn only from dates the API returned for a complaint date the user entered (the caller
 * checks); the list below carries the same dates with their rule quotes, so the picture is never the only source.
 */
export function DeadlineTimeline({ d, today = localToday() }: { d: Deadlines; today?: string }) {
  const { t } = useSession();
  const reduce = useReducedMotion();
  const rows: Row[] = [];
  if (d.letter_date?.iso && d.insurer_reply_by?.iso) rows.push({ id: "reply", label: t("d1"), start: d.letter_date, end: d.insurer_reply_by });
  if (d.ombudsman_earliest?.iso && d.ombudsman_latest?.iso) {
    rows.push({ id: "ombudsman", label: t("dl_window" as Key), start: d.ombudsman_earliest, end: d.ombudsman_latest });
  }
  if (!rows.length) return null;

  const lo = Math.min(at(today), ...rows.map((r) => at(r.start.iso)));
  const hi = Math.max(at(today), ...rows.map((r) => at(r.end.iso)));
  const span = Math.max(hi - lo, DAY);
  const pct = (iso: string) => ((at(iso) - lo) / span) * 100;
  const todayPct = pct(today);
  const todayDisplay = today.split("-").reverse().join("/");

  const status = (r: Row) => {
    const left = daysUntil(r.end.iso, today);
    if (left < 0) return t("dl_passed" as Key);
    if (r.id === "ombudsman" && daysUntil(r.start.iso, today) > 0) return fill(t("dl_opens_in" as Key), { n: daysUntil(r.start.iso, today) });
    return fill(t("dl_days_left" as Key), { n: left });
  };
  const grow = (i: number) =>
    reduce
      ? {}
      : { initial: { scaleX: 0 }, whileInView: { scaleX: 1 }, viewport: { once: true }, transition: { duration: 0.9, ease: EASE, delay: 0.15 + i * 0.25 } };

  return (
    <figure
      role="img"
      className="dl-chart"
      aria-label={`${rows.map((r) => `${r.label}: ${r.start.display} – ${r.end.display}. ${status(r)}.`).join(" ")} ${t("dl_today" as Key)}: ${todayDisplay}`}
    >
      <div className="dl-rows">
        {rows.map((r, i) => (
          <div key={r.id} className="dl-row" data-row={r.id}>
            <div className="dl-row-head">
              <span className="dl-row-label">{r.label}</span>
              <span className="dl-row-status" data-status>
                {status(r)}
              </span>
            </div>
            <div className="dl-track">
              <motion.span
                className="dl-bar"
                data-row={r.id}
                style={{ left: `${pct(r.start.iso)}%`, width: `${Math.max(pct(r.end.iso) - pct(r.start.iso), 1.5)}%`, originX: 0 }}
                {...grow(i)}
              />
              <motion.span
                className="dl-now"
                style={{ left: `calc(${todayPct}% - 1.5px)` }}
                {...(reduce ? {} : { initial: { opacity: 0, y: -8 }, whileInView: { opacity: 1, y: 0 }, viewport: { once: true }, transition: { delay: 0.9, duration: 0.4, ease: EASE } })}
              />
            </div>
            {/* the window's own dates, written under the bar where it starts (kept inside the track at the right edge) */}
            <div className="dl-ends">
              <span style={{ marginInlineStart: `min(${pct(r.start.iso)}%, calc(100% - 12.5rem))` }}>
                {r.start.display} – {r.end.display}
              </span>
            </div>
          </div>
        ))}
      </div>
      <figcaption className="dl-cap">
        <span aria-hidden="true" className="dl-cap-mark" />
        {t("dl_today" as Key)}: {todayDisplay}
      </figcaption>
    </figure>
  );
}
