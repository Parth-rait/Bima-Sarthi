import { useState } from "react";
import type { PolicyTerm, PolicyView } from "../api";
import { pick } from "../i18n";
import { valText as polValText } from "../lib/facts";
import { describeError, type ViewError } from "../lib/errors";
import { useSession } from "../state/store";
import { ErrorBox } from "./ErrorBox";
import { FilePicker } from "./FilePicker";
import { Field, Quote } from "./evidence";

function PolTag({ term }: { term: PolicyTerm }) {
  const { t } = useSession();
  const key = ({ found: "pol_found", confirmed: "pol_confirmed", entered: "pol_entered" } as const)[
    term.state as "found" | "confirmed" | "entered"
  ];
  if (key) return <span className="tag tag-ok">{t(key)}</span>;
  if (term.state === "absent") return null;
  return <span className="tag tag-need">{t("need")}</span>;
}

function TermBody({ term }: { term: PolicyTerm }) {
  const { state, t } = useSession();
  const lang = state.lang;
  return (
    <>
      <h4>
        {pick(term.label, lang)} <PolTag term={term} />
      </h4>
      {term.display ? (
        <p className="term-value">{pick(term.display, lang)}</p>
      ) : (
        <p className="muted">{pick(term.message, lang)}</p>
      )}
      {term.quote ? (
        <Quote source={`${t("src")}${term.page_no != null ? ` (${t("page")} ${term.page_no})` : ""}`}>{term.quote}</Quote>
      ) : null}
    </>
  );
}

/** Result screen: "What your policy says", read only. Never feeds the check. */
export function PolicySection({ policy }: { policy: PolicyView }) {
  const { state, t } = useSession();
  return (
    <section className="block" aria-labelledby="pol-h" id="policy-section">
      <h3 id="pol-h">{pick(policy.heading, state.lang)}</h3>
      <p className="hint">{pick(policy.disclaimer, state.lang)}</p>
      <ul className="terms">
        {policy.terms.map((term) => (
          <li key={term.key} data-key={term.key}>
            <TermBody term={term} />
          </li>
        ))}
      </ul>
      <span className="sr-only">{t("pol_section_note")}</span>
    </section>
  );
}

/** Confirm screen: upload, review, edit and remove the optional policy key terms. */
export function PolicyBox() {
  const { state, actions, t } = useSession();
  const { policy, lang } = state;
  const [files, setFiles] = useState<File[]>([]);
  const [err, setErr] = useState<ViewError | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [confirms, setConfirms] = useState<Record<string, boolean>>({});
  const [removed, setRemoved] = useState(false);
  const busy = state.busy === "policy" || state.busy === "facts";
  const label = (k: string) => policy?.terms.find((x) => x.key === k)?.label.en ?? k;

  const read = async () => {
    setErr(null);
    setRemoved(false);
    if (!files.length || !state.sid) return;
    const out = await actions.policyExtract(files);
    if (out.ok) {
      setFiles([]);
      setEdits({});
      setConfirms({});
    } else setErr(describeError(out.error, t, label));
  };
  const save = async () => {
    setErr(null);
    if (!policy) return;
    const terms: Record<string, { value?: unknown; confirm?: boolean }> = {};
    for (const x of policy.terms) {
      const shown = polValText(x.value);
      const cur = edits[x.key];
      if (cur !== undefined && cur !== shown && cur.trim()) terms[x.key] = { value: cur };
      else if (confirms[x.key]) terms[x.key] = { confirm: true };
    }
    if (!Object.keys(terms).length) return;
    const out = await actions.policySave({ terms });
    if (out.ok) {
      setEdits({});
      setConfirms({});
    } else setErr(describeError(out.error, t, label));
  };
  const remove = async () => {
    setErr(null);
    const out = await actions.policyRemove();
    if (out.ok) {
      setRemoved(true);
      setEdits({});
      setConfirms({});
    } else setErr(describeError(out.error, t, label));
  };

  return (
    <section className="block" id="policy-box" aria-labelledby="pol-up-h">
      <h3 id="pol-up-h">{t("pol_up_h")}</h3>
      <p className="hint">{t("pol_up_p")}</p>
      <FilePicker files={files} onChange={setFiles} label={t("pol_l")} inputId="policy-files" disabled={busy} />
      <div className="actions">
        <button type="button" onClick={read} disabled={busy || files.length === 0 || !state.sid}>
          {t("pol_b")}
        </button>
      </div>
      <p role="status" className="status">
        {state.busy === "policy" ? t("pol_reading") : removed ? t("pol_removed") : ""}
      </p>
      {err ? <ErrorBox message={err.message} items={err.items} /> : null}
      {policy && policy.terms ? (
        <div className="policy-terms">
          <h3>{pick(policy.heading, lang)}</h3>
          <p className="hint">{pick(policy.disclaimer, lang)}</p>
          <ul className="terms">
            {policy.terms.map((x) => {
              const shown = !!x.display;
              const fieldErr = err?.fieldErrors[x.key];
              return (
                <li key={x.key} data-key={x.key} className={x.state === "unverified" || x.state === "conflict" ? "pending" : undefined}>
                  <TermBody term={x} />
                  <Field label={shown ? t("edit") : t("pol_enter")} error={fieldErr}>
                    {(p) => (
                      <input
                        {...p}
                        type="text"
                        value={edits[x.key] ?? polValText(x.value)}
                        onChange={(e) => setEdits({ ...edits, [x.key]: e.target.value })}
                      />
                    )}
                  </Field>
                  {x.state === "found" ? (
                    <label className="check">
                      <input
                        type="checkbox"
                        checked={!!confirms[x.key]}
                        onChange={(e) => setConfirms({ ...confirms, [x.key]: e.target.checked })}
                      />
                      <span>{t("confirm")}</span>
                    </label>
                  ) : null}
                </li>
              );
            })}
          </ul>
          <div className="actions">
            <button type="button" onClick={save} disabled={busy}>
              {t("pol_save")}
            </button>
            <button type="button" className="danger" onClick={remove} disabled={busy}>
              {t("pol_remove")}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
