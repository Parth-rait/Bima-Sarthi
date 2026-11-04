import { useEffect, useState } from "react";
import { api, type EvidenceMethod, type EvidenceSummary } from "@/api";
import { Button } from "@/components/ds/Button";
import { ErrorState } from "@/components/ds/ErrorState";
import { Loader } from "@/components/ds/Loader";
import { PageHeader } from "@/components/ds/PageHeader";
import { Section } from "@/components/ds/Section";
import { useSession } from "@/state/store";

const pct = (x: number | null | undefined) => (x == null ? null : `${Math.round(x * 100)}%`);

function Tile({ value, label, note }: { value: string; label: string; note?: string }) {
  return (
    <li className=" pt-4">
      <span
        className={
          /\d/.test(value)
            ? "block font-display text-[2.25rem] font-medium leading-none text-ink"
            : "block font-display text-[1.375rem] font-medium leading-tight text-ink-soft"
        }
      >
        {value}
      </span>
      <span className="mt-2 block font-semibold text-ink">{label}</span>
      {note ? <span className="mt-1 block text-[0.9375rem] text-ink-soft">{note}</span> : null}
    </li>
  );
}

function RulesNumbers({ m, s }: { m: EvidenceMethod; s: EvidenceSummary }) {
  const measurable = m.scorable_findings > 0;
  return (
    <>
      <ul className="m-0 mt-6 grid list-none gap-x-8 gap-y-6 p-0 sm:grid-cols-2 lg:grid-cols-4" data-testid="evidence-tiles">
        <Tile value={String(s.n_cases)} label="Real cases evaluated" note={`${s.n_eligible} produced an engine answer`} />
        <Tile
          value={measurable && m.agreement ? `${m.agreement.agree}/${m.agreement.of}` : "Not measurable yet"}
          label="Agreement with the court"
          note={measurable ? undefined : "0 findings could be scored against a reviewed holding"}
        />
        <Tile
          value={m.false_hope_rate ? `${m.false_hope_rate.false_hope}/${m.false_hope_rate.of}` : "Not measurable yet"}
          label="False hope"
          note={m.false_hope_rate ? "We said challengeable; the court held for the insurer" : "No challengeable finding met a reviewed holding"}
        />
        <Tile value={pct(m.quote_coverage) ?? "n/a"} label="Quote coverage" note="Answers that carry their rule's verbatim quote and page" />
      </ul>
      <ul className="m-0 mt-6 grid list-none gap-x-8 gap-y-6 p-0 sm:grid-cols-2 lg:grid-cols-4">
        <Tile value={String(m.abstained_findings)} label="Findings answered “Need info”" note="The engine asked for a fact instead of guessing" />
        <Tile
          value={m.safe_abstention ? `${m.safe_abstention.safe}/${m.safe_abstention.of}` : "n/a"}
          label="Safe abstentions"
          note="Out-of-scope cases where the engine never said challengeable"
        />
        <Tile value={pct(m.stability) ?? "n/a"} label="Stability" note={`Same answer over ${s.repeats} repeats`} />
        <Tile value={m.cost_usd === 0 ? "None" : `US$${m.cost_usd.toFixed(2)}`} label="Model cost" note="The rules make no model call" />
      </ul>
    </>
  );
}

/**
 * The published evaluation, read from GET /api/evidence (docs/eval/summary.json, written by `cli eval`).
 * A rate is shown only when it was computed; otherwise the page says it is not measurable yet and why.
 */
export default function Evidence() {
  const { t } = useSession();
  const [s, setS] = useState<EvidenceSummary | null>(null);
  const [failed, setFailed] = useState(false);
  const [missing, setMissing] = useState(false);

  const load = () => {
    setFailed(false);
    api
      .evidence()
      .then(setS)
      .catch((e: { status?: number; kind?: string }) => (e?.kind === "expired" || e?.status === 404 ? setMissing(true) : setFailed(true)));
  };
  useEffect(load, []);

  const rules = s?.methods.rules;
  return (
    <>
      <PageHeader
        title="How well the rules agree with real judgments"
        lead="We run the rule engine on real consumer-commission and court judgments, using facts a person has reviewed, and compare its answer with how the forum decided. These are the measured numbers, with what they can and cannot show."
      >
        <p className="mb-0 mt-3 text-[0.9375rem] text-ink-soft">{t("editorial_note")}</p>
      </PageHeader>

      <Section labelledBy="ev-h">
        <h2 id="ev-h" className="m-0 font-display text-h2 font-medium text-ink">
          The latest run
        </h2>
        {!s && !failed && !missing ? (
          <div className="mt-6">
            <Loader label={t("loading")} />
          </div>
        ) : null}
        {missing ? <p className="mt-4">No evaluation has been published yet.</p> : null}
        {failed ? (
          <ErrorState title={t("err")} what="The evaluation summary could not load." next={t("cases_retry_next")} className="mt-4">
            <Button variant="secondary" onClick={load}>
              {t("svc_retry")}
            </Button>
          </ErrorState>
        ) : null}
        {s && rules ? (
          <>
            <p className="mb-0 mt-3 text-ink-soft">
              Run {s.run_id ?? "unnamed"}, {s.generated_on.split("-").reverse().join("/")}. Rules method only.
            </p>
            <RulesNumbers m={rules} s={s} />
            {rules.scorable_findings === 0 ? (
              <div className="mt-8 max-w-[68ch] pt-5">
                <h3 className="m-0 font-display text-h3 font-medium text-ink">Why agreement is not shown</h3>
                <p className="mb-0 mt-2">
                  On every reviewed case so far the engine answered “Need info”: a fact it needs is missing from the reviewed record, so it asked
                  instead of guessing. An answer that asks cannot be right or wrong against the court, so there is no agreement or false-hope number
                  to publish. The next step is human review of more case facts, not a different calculation.
                </p>
              </div>
            ) : null}
            <div className="mt-8 max-w-[68ch] pt-5">
              <h3 className="m-0 font-display text-h3 font-medium text-ink">Limits</h3>
              <p className="mb-0 mt-2">{s.limitation}</p>
              <p className="mb-0 mt-2">
                Of {s.n_cases} cases: {s.n_skipped_unresolved} were skipped because a needed fact is not reviewed yet, {s.n_out_of_scope} had no rule in
                force on the claim date, and {s.n_no_usable} had no usable rejection reason or rule. Those go to a person, never to a verdict.
              </p>
            </div>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button to="/cases">{t("cases_h")}</Button>
              <Button to="/check-claim" variant="secondary">
                {t("nav_check")}
              </Button>
            </div>
          </>
        ) : null}
      </Section>
    </>
  );
}
