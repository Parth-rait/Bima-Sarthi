import { describe, expect, it } from "vitest";
import { buildPayload, initialForm, needsContinuity, unresolvedKeys, visibleFacts } from "../lib/confirm";
import { effectiveProduct, initialState } from "../state/session";
import { FACTS, fact } from "./fixtures";

describe("confirm-screen gating", () => {
  it("lists the rejection reason even when the API sent none, pending first", () => {
    const rows = visibleFacts({ inception_date: FACTS.inception_date });
    expect(rows.map(([k]) => k)).toEqual(["rejection_ground", "inception_date"]);
    expect(rows[0][1].status).toBe("needs_confirmation");
  });

  it("blocks the check while any needs_confirmation fact is unanswered", () => {
    const form = initialForm(FACTS);
    expect(unresolvedKeys(FACTS, form).sort()).toEqual(["fraud_alleged", "rejection_ground"].sort());
  });

  it("an absence boolean needs an explicit answer: it is never pre-selected", () => {
    const form = initialForm(FACTS);
    expect(form.bools.fraud_alleged).toBe("");
    form.bools.fraud_alleged = "no";
    expect(unresolvedKeys(FACTS, form)).toEqual(["rejection_ground"]);
  });

  it("the extracted rejection reason is pre-filled but needs the user's tick or a different choice", () => {
    const form = initialForm(FACTS);
    expect(form.ground).toBe("pre_existing_disease");
    form.bools.fraud_alleged = "no";
    expect(unresolvedKeys(FACTS, form)).toEqual(["rejection_ground"]);
    form.confirmed.rejection_ground = true;
    expect(unresolvedKeys(FACTS, form)).toEqual([]);
    form.confirmed.rejection_ground = false;
    form.ground = "room_rent";
    expect(unresolvedKeys(FACTS, form)).toEqual([]);
    form.ground = "pre_existing_disease";
    form.confirmed.rejection_ground = true;
    const body = buildPayload(FACTS, form, "health");
    expect(body.facts.rejection_ground).toEqual({ value: "pre_existing_disease" });
    expect(body.facts.fraud_alleged).toEqual({ value: "no" });
    expect(body.facts.product_line).toEqual({ value: "health" });
  });

  it("a pending text fact needs the confirm tick, or an edit", () => {
    const facts = { ...FACTS, rejection_ground: { ...FACTS.rejection_ground, status: "user_confirmed" as const }, claim_date: fact("claim_date", { value: "05/03/2024", status: "needs_confirmation" }) };
    const form = initialForm(facts);
    form.bools.fraud_alleged = "no";
    expect(unresolvedKeys(facts, form)).toEqual(["claim_date"]);
    form.confirmed.claim_date = true;
    expect(unresolvedKeys(facts, form)).toEqual([]);
    expect(buildPayload(facts, form, "health").facts.claim_date).toEqual({ confirm: true });
    form.confirmed.claim_date = false;
    form.text.claim_date = "06/03/2024";
    expect(unresolvedKeys(facts, form)).toEqual([]);
    expect(buildPayload(facts, form, "health").facts.claim_date).toEqual({ value: "06/03/2024" });
  });

  it("an empty pending value cannot be confirmed", () => {
    const facts = { claim_date: fact("claim_date", { value: null, status: "needs_confirmation" }), rejection_ground: { ...FACTS.rejection_ground, status: "user_confirmed" as const } };
    const form = initialForm(facts);
    form.confirmed.claim_date = true;
    expect(unresolvedKeys(facts, form)).toEqual(["claim_date"]);
  });

  it("tri-state continuity: unanswered sends nothing, Not sure clears, Yes/No send booleans", () => {
    const facts = { ...FACTS, continuity_confirmed: fact("continuity_confirmed", { value: true, status: "user_confirmed" }) };
    const form = initialForm(facts);
    form.bools.fraud_alleged = "no";
    form.cont = "";
    expect(buildPayload(facts, form, "health").facts).not.toHaveProperty("continuity_confirmed");
    form.cont = "unsure";
    expect(buildPayload(facts, form, "health").facts.continuity_confirmed).toEqual({ clear: true });
    form.cont = "no";
    expect(buildPayload(facts, form, "health").facts.continuity_confirmed).toEqual({ value: false });
    // Not sure with nothing stored sends nothing at all
    const none = initialForm(FACTS);
    none.cont = "unsure";
    expect(buildPayload(FACTS, none, "health").facts).not.toHaveProperty("continuity_confirmed");
  });

  it("asks for continuity only when it matters", () => {
    expect(needsContinuity(FACTS)).toBe(true); // pre_existing_disease
    expect(needsContinuity({ rejection_ground: fact("rejection_ground", { value: "room_rent" }) })).toBe(false);
  });

  it("missing dates are only sent when typed", () => {
    const form = initialForm(FACTS);
    expect(buildPayload(FACTS, form, "health").facts).not.toHaveProperty("claim_date");
    form.added.claim_date = " 05/03/2024 ";
    expect(buildPayload(FACTS, form, "health").facts.claim_date).toEqual({ value: "05/03/2024" });
  });
});

describe("product-line gating", () => {
  it("nothing is chosen unless the user, a stored value or the server hint says so", () => {
    expect(effectiveProduct(initialState())).toBe("");
    expect(effectiveProduct(initialState({ productHint: "health" }))).toBe("health");
    expect(effectiveProduct(initialState({ productHint: "nonsense" }))).toBe("");
  });
  it("the user's choice beats the hint, including choosing 'nothing'", () => {
    expect(effectiveProduct(initialState({ productHint: "health", productChoice: "motor" }))).toBe("motor");
    expect(effectiveProduct(initialState({ productHint: "health", productChoice: "" }))).toBe("");
  });
  it("a stored product_line fact is used", () => {
    expect(effectiveProduct(initialState({ facts: { product_line: fact("product_line", { value: "life" }) } }))).toBe("life");
  });
});

describe("free-text rejection reasons from the reader", () => {
  it("are not a listed ground: the user must choose one, and the free text is never sent", () => {
    const facts = { ...FACTS, rejection_ground: { ...FACTS.rejection_ground, value: "non-disclosure: diabetes was not declared" }, fraud_alleged: { ...FACTS.fraud_alleged, status: "user_confirmed" as const } };
    const form = initialForm(facts);
    expect(form.ground).toBe("");
    expect(unresolvedKeys(facts, form)).toEqual(["rejection_ground"]);
    form.ground = "non_disclosure";
    expect(unresolvedKeys(facts, form)).toEqual([]);
    expect(buildPayload(facts, form, "health").facts.rejection_ground).toEqual({ value: "non_disclosure" });
  });
});
