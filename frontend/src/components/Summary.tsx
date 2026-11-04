import type { Finding, Verdict } from "../api";
import { useSession } from "../state/store";
import { Button } from "./ds/Button";
import { Stamp } from "./evidence";

const VERDICTS: Verdict[] = ["CHALLENGEABLE", "NEED_INFO", "CONSISTENT"];

/**
 * The result at a glance, sticking under the stepper while a long report scrolls past: how many findings, of
 * which kinds, and the one action that follows from them. The numbers and words sit on a solid plate — the
 * blur is only ever behind the plate, never behind text.
 */
export function ResultSummary({ findings }: { findings: Finding[] }) {
  const { t } = useSession();
  const count = (v: Verdict) => findings.filter((f) => f.verdict === v).length;
  return (
    <aside className="rail" aria-labelledby="rail-h">
      <div className="rail-plate">
        <h3 id="rail-h">{t("rail_h")}</h3>
        <ul className="rail-counts">
          {VERDICTS.map((v) => (
            <li key={v} className="rail-count">
              <Stamp verdict={v} />
              <span className="rail-n">{count(v)}</span>
            </li>
          ))}
        </ul>
        <p className="rail-next">{t("rail_next")}</p>
        <Button to="/action-plan" variant="primary" size="sm" className="rail-cta">
          {t("open_plan")}
        </Button>
      </div>
    </aside>
  );
}
