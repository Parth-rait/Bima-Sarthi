import { useEffect, useMemo, useRef, useState } from "react";
import type { Fact } from "../api";
import { ErrorBox } from "../components/ErrorBox";
import { PolicyBox } from "../components/Policy";
import { Choice, Field, Quote, Stitch } from "../components/evidence";
import { GROUND_LABEL, PRODUCT_KEYS, PRODUCT_LABEL, REJECTION_GROUNDS, type ProductLine } from "../i18n";
import {
  ADD_KEYS,
  LETTER_FIELDS,
  buildPayload,
  initialForm,
  isBoolFact,
  isPending,
  knownGround,
  needsContinuity,
  unresolvedKeys,
  visibleFacts,
  type ConfirmForm,
} from "../lib/confirm";
import { describeError, type ViewError } from "../lib/errors";
import { isDeductionList, labelOf, valText } from "../lib/facts";
import { rowOrder } from "../lib/motion";
import { effectiveProduct } from "../state/session";
import { useSession } from "../state/store";

export function ConfirmScreen() {
  const { state, actions, t } = useSession();
  const { facts, lang } = state;
  const [form, setForm] = useState<ConfirmForm>(() => initialForm(facts));
  const [err, setErr] = useState<ViewError | null>(null);
  const [unresolved, setUnresolved] = useState<string[]>([]);
  const errRef = useRef<HTMLDivElement>(null);
  const productRef = useRef<HTMLSelectElement>(null);
  const product = effectiveProduct(state);
  const hinted = state.productChoice === null && !state.facts.product_line && !!state.productHint && product === state.productHint;
  const busy = state.busy === "facts" || state.busy === "check" || state.busy === "explain";

  const label = (k: string) => labelOf(k, lang, { facts, labels: state.labels, policy: state.policy });
  const rows = useMemo(() => visibleFacts(facts), [facts]);
  const upd = (patch: Partial<ConfirmForm>) => setForm((f) => ({ ...f, ...patch }));
  const flagged = new Set([...(err?.flagged ?? []), ...unresolved]);

  useEffect(() => {
    if (!err) return;
    if (err.productMissing) productRef.current?.focus();
    else errRef.current?.focus();
  }, [err]);

  const run = async () => {
    setErr(null);
    setUnresolved([]);
    if (!product) {
      setErr({ message: t("pl_need"), items: [], fieldErrors: {}, flagged: [], productMissing: true, canEnterManually: false, expired: false });
      return;
    }
    const open = unresolvedKeys(facts, form);
    if (open.length) {
      setUnresolved(open);
      setErr({ message: t("unanswered"), items: open.map(label), fieldErrors: {}, flagged: open, productMissing: false, canEnterManually: false, expired: false });
      return;
    }
    const out = await actions.saveAndCheck(buildPayload(facts, form, product as ProductLine));
    if (!out.ok) {
      setErr(describeError(out.error, t, label));
    }
  };

  const fe = (k: string): string | null => err?.fieldErrors[k] ?? (flagged.has(k) ? t("unanswered_item") : null);

  return (
    <section aria-labelledby="h-confirm" className="screen">
      <h2 id="h-confirm" tabIndex={-1} data-screen-heading>
        {t("cf_h")}
      </h2>
      <p className="lede">{t("cf_p")}</p>

      <div className="block">
        <Field
          label={t("pl_label")}
          hint={
            <>
              {hinted ? <span className="hint-line">{t("pl_hint")}</span> : null}
              <span className="hint-line">{t("pl_why")}</span>
            </>
          }
          error={err?.productMissing ? t("pl_need") : err?.fieldErrors.product_line}
        >
          {(p) => (
            <select
              {...p}
              ref={productRef}
              value={product}
              onChange={(e) => actions.setProductChoice(e.target.value as ProductLine | "")}
            >
              <option value="">{t("pl_choose")}</option>
              {PRODUCT_KEYS.map((k) => (
                <option key={k} value={k}>
                  {PRODUCT_LABEL[lang][k]}
                </option>
              ))}
            </select>
          )}
        </Field>
      </div>

      <ul className="facts">
        {rows.map(([k, f], i) => (
          <FactRow
            key={k}
            i={i}
            k={k}
            f={f}
            form={form}
            upd={upd}
            label={label(k)}
            error={fe(k)}
          />
        ))}
      </ul>

      <Stitch />
      <section className="block" aria-labelledby="h-add">
        <h3 id="h-add">{t("add_h")}</h3>
        <p className="hint">{t("add_p")}</p>
        <div className="grid2">
          {ADD_KEYS.filter((k) => !facts[k]).map((k) => (
            <Field key={k} label={label(k)} error={err?.fieldErrors[k]}>
              {(p) => (
                <input
                  {...p}
                  type="text"
                  inputMode="numeric"
                  placeholder="DD/MM/YYYY"
                  value={form.added[k] ?? ""}
                  onChange={(e) => upd({ added: { ...form.added, [k]: e.target.value } })}
                />
              )}
            </Field>
          ))}
        </div>
      </section>

      <Stitch />
      <PolicyBox />

      <Stitch />
      <section className="block" aria-labelledby="h-more">
        <h3 id="h-more">{t("more")}</h3>
        <div className="grid2">
          {LETTER_FIELDS.map(([k, lk]) => {
            const f = facts[k];
            return (
              <Field key={k} label={t(lk)} error={err?.fieldErrors[k]}>
                {(p) => (
                  <>
                    <input
                      {...p}
                      type="text"
                      value={form.letter[k] ?? ""}
                      onChange={(e) => upd({ letter: { ...form.letter, [k]: e.target.value } })}
                    />
                    {f?.quote ? (
                      <Quote source={`${t("src")}${f.page_no != null ? ` (${t("page")} ${f.page_no})` : ""}`}>{f.quote}</Quote>
                    ) : null}
                  </>
                )}
              </Field>
            );
          })}
        </div>
        <Field label={t("replydate")} error={err?.fieldErrors.insurer_reply_date}>
          {(p) => (
            <input
              {...p}
              type="text"
              inputMode="numeric"
              placeholder="DD/MM/YYYY"
              value={form.reply}
              onChange={(e) => upd({ reply: e.target.value })}
            />
          )}
        </Field>
        {needsContinuity(facts) ? (
          <Choice
            legend={t("cont")}
            name="cont"
            value={form.cont}
            onChange={(v) => upd({ cont: v as ConfirmForm["cont"] })}
            error={err?.fieldErrors.continuity_confirmed ?? (flagged.has("continuity_confirmed") ? t("unanswered_item") : null)}
            options={[
              { value: "yes", label: t("yes") },
              { value: "no", label: t("no") },
              { value: "unsure", label: t("notsure") },
            ]}
          />
        ) : null}
      </section>

      <ErrorBox boxRef={errRef} message={err?.message ?? null} items={err?.items} />
      <p role="status" className="status">
        {state.busy === "facts" ? t("saving") : state.busy === "check" ? t("checking") : state.busy === "explain" ? t("checking") : ""}
        {busy && state.slow ? ` ${t("slow")}` : ""}
      </p>
      <div className="actions">
        <button type="button" id="run-check" onClick={run} disabled={busy}>
          {t("run")}
        </button>
        <button type="button" className="secondary" onClick={() => actions.goto("upload")} disabled={busy}>
          {t("back")}
        </button>
      </div>
    </section>
  );
}

function SourceLine({ f }: { f: Fact }) {
  const { t } = useSession();
  return (
    <Quote
      source={
        <>
          {t("src")}
          {f.page_no != null ? ` (${t("page")} ${f.page_no})` : ""}
        </>
      }
    >
      {f.quote || <span className="muted">{t("none")}</span>}
    </Quote>
  );
}

function FactRow({
  k,
  i,
  f,
  form,
  upd,
  label,
  error,
}: {
  k: string;
  i: number;
  f: Fact;
  form: ConfirmForm;
  upd: (p: Partial<ConfirmForm>) => void;
  label: string;
  error: string | null;
}) {
  const { state, t } = useSession();
  const pend = isPending(f);
  const tagText = pend ? t("need") : f.status === "user_confirmed" ? t("done") : t("ok_read");
  let control: React.ReactNode;

  if (k === "rejection_ground") {
    control = (
      <>
        <Field label={t("edit")} error={error}>
          {(p) => (
            <select {...p} value={form.ground} onChange={(e) => upd({ ground: e.target.value })}>
              <option value="">{t("choose")}</option>
              {REJECTION_GROUNDS.map((g) => (
                <option key={g} value={g}>
                  {GROUND_LABEL[state.lang][g]}
                </option>
              ))}
            </select>
          )}
        </Field>
        {typeof f.value === "string" && f.value && !knownGround(f.value) ? (
          <p className="hint">
            {t("ok_read")}: {f.value}
          </p>
        ) : null}
        {pend && knownGround(f.value) ? <ConfirmBox k={k} form={form} upd={upd} error={null} /> : null}
      </>
    );
  } else if (isBoolFact(k, f)) {
    control = (
      <Choice
        legend={t("edit")}
        name={`b-${k}`}
        value={form.bools[k] ?? ""}
        onChange={(v) => upd({ bools: { ...form.bools, [k]: v as "yes" | "no" } })}
        error={error}
        options={[
          { value: "yes", label: t("yes") },
          { value: "no", label: t("no") },
        ]}
      />
    );
  } else if (k === "deductions" && isDeductionList(f.value)) {
    control = (
      <>
        {f.value.map((it, i) => (
          <Choice
            key={i}
            legend={`${String(it.item ?? "")}${it.amount != null ? ` — ${String(it.amount)}` : ""} — ${t("listed_q")}`}
            name={`d-${i}`}
            value={form.deductions[k]?.[i] ?? "unsure"}
            onChange={(v) => {
              const next = [...(form.deductions[k] ?? [])];
              next[i] = v as "yes" | "no" | "unsure";
              upd({ deductions: { ...form.deductions, [k]: next } });
            }}
            options={[
              { value: "yes", label: t("yes") },
              { value: "no", label: t("no") },
              { value: "unsure", label: t("notsure") },
            ]}
          />
        ))}
        <ConfirmBox k={k} form={form} upd={upd} error={error} />
      </>
    );
  } else {
    control = (
      <>
        <Field label={t("edit")} error={error}>
          {(p) => (
            <input
              {...p}
              type="text"
              value={form.text[k] ?? valText(f.value)}
              onChange={(e) => upd({ text: { ...form.text, [k]: e.target.value } })}
            />
          )}
        </Field>
        <ConfirmBox k={k} form={form} upd={upd} error={null} />
      </>
    );
  }

  return (
    <li id={`fact-${k}`} data-key={k} style={rowOrder(i)} className={`fact${pend ? " pending" : ""}${error ? " has-error" : ""}`}>
      <div className="fact-src">
        <h3>
          {label} <span className={`tag ${pend ? "tag-need" : "tag-ok"}`}>{tagText}</span>
        </h3>
        <SourceLine f={f} />
      </div>
      <div className="fact-edit">{control}</div>
    </li>
  );
}

function ConfirmBox({ k, form, upd, error }: { k: string; form: ConfirmForm; upd: (p: Partial<ConfirmForm>) => void; error: string | null }) {
  const { t } = useSession();
  return (
    <>
      <label className="check">
        <input
          type="checkbox"
          id={`c-${k}`}
          checked={!!form.confirmed[k]}
          onChange={(e) => upd({ confirmed: { ...form.confirmed, [k]: e.target.checked } })}
        />
        <span>{t("confirm")}</span>
      </label>
      {error ? <p className="field-error">{error}</p> : null}
    </>
  );
}
