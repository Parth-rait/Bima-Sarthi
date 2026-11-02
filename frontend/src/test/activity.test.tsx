import { act, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CompanionSlot } from "../companion/CompanionSlot";
import { APP_ACTIVITIES, deriveActivity, type ActivityInputs } from "../state/activity";
import { useSession } from "../state/store";
import { mockFetch } from "./mockFetch";
import { renderIn } from "./render";
import { FACTS, check, explain } from "./fixtures";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const base: ActivityInputs = { view: "upload", busy: null, slow: false, lastError: null, pendingCount: 0, productChosen: false };

describe("appActivity derivation (the companion's only input)", () => {
  it("defines exactly the eight states", () => {
    expect([...APP_ACTIVITIES].sort()).toEqual(["completed", "error", "idle", "needs_input", "processing", "reading", "thinking", "waiting"]);
  });
  it("idle on the upload screen with nothing in flight", () => {
    expect(deriveActivity(base)).toBe("idle");
  });
  it("reading while documents are being read", () => {
    expect(deriveActivity({ ...base, busy: "extract" })).toBe("reading");
    expect(deriveActivity({ ...base, busy: "policy" })).toBe("reading");
  });
  it("thinking while the explanation is produced", () => {
    expect(deriveActivity({ ...base, view: "result", busy: "explain" })).toBe("thinking");
  });
  it("processing for saves, the check, the letter", () => {
    for (const busy of ["facts", "check", "letter", "gallery", "delete", "session"] as const) {
      expect(deriveActivity({ ...base, view: "confirm", busy })).toBe("processing");
    }
  });
  it("waiting once a request is slow, whatever it is", () => {
    expect(deriveActivity({ ...base, busy: "extract", slow: true })).toBe("waiting");
    expect(deriveActivity({ ...base, busy: "check", slow: true })).toBe("waiting");
  });
  it("needs_input on the confirm screen while facts are pending or no insurance type is chosen", () => {
    expect(deriveActivity({ ...base, view: "confirm", pendingCount: 2, productChosen: true })).toBe("needs_input");
    expect(deriveActivity({ ...base, view: "confirm", pendingCount: 0, productChosen: false })).toBe("needs_input");
    expect(deriveActivity({ ...base, view: "confirm", pendingCount: 0, productChosen: true })).toBe("idle");
  });
  it("asking the user for more (409/422) is needs_input, not error", () => {
    for (const lastError of ["needs_confirmation", "needs_product_line", "validation"] as const) {
      expect(deriveActivity({ ...base, view: "confirm", productChosen: true, lastError })).toBe("needs_input");
    }
  });
  it("error for failures the user did not cause", () => {
    for (const lastError of ["reader_unavailable", "network", "expired", "unknown"] as const) {
      expect(deriveActivity({ ...base, lastError })).toBe("error");
    }
  });
  it("completed once the result is on screen", () => {
    expect(deriveActivity({ ...base, view: "result" })).toBe("completed");
  });
  it("in-flight work wins over an old error", () => {
    expect(deriveActivity({ ...base, lastError: "network", busy: "extract" })).toBe("reading");
  });
});

describe("CompanionSlot", () => {
  it("renders nothing (the mascot is a later phase)", () => {
    const { container } = renderIn(<CompanionSlot />);
    expect(container.innerHTML).toBe("");
  });
  it("renders nothing for every activity", () => {
    for (const a of APP_ACTIVITIES) {
      const { container, unmount } = renderIn(<CompanionSlot activity={a} />);
      expect(container.innerHTML).toBe("");
      unmount();
    }
  });
});

function Probe() {
  const { activity, actions } = useSession();
  return (
    <>
      <output data-testid="act">{activity}</output>
      <button onClick={() => void actions.saveAndCheck({ facts: { product_line: { value: "health" } } })}>go</button>
    </>
  );
}

describe("activity follows real app events", () => {
  it("goes processing during the check, then completed on the result", async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((r) => (release = r));
    mockFetch({
      "PUT /session/s1/facts": () => ({ json: { facts: FACTS, needs_confirmation: [] } }),
      "POST /session/s1/check": async () => {
        await gate;
        return { json: check() };
      },
      "POST /session/s1/explain": () => ({ json: explain() }),
    });
    renderIn(<Probe />, { sid: "s1", view: "confirm", facts: FACTS });
    expect(screen.getByTestId("act").textContent).toBe("needs_input");
    act(() => screen.getByText("go").click());
    await waitFor(() => expect(screen.getByTestId("act").textContent).toBe("processing"));
    await act(async () => release());
    await waitFor(() => expect(screen.getByTestId("act").textContent).toBe("completed"));
  });

  it("becomes waiting after the slow threshold", async () => {
    vi.useFakeTimers();
    mockFetch({
      "PUT /session/s1/facts": () => new Promise(() => {}),
    });
    renderIn(<Probe />, { sid: "s1", view: "confirm", facts: FACTS });
    act(() => screen.getByText("go").click());
    expect(screen.getByTestId("act").textContent).toBe("processing");
    await act(async () => {
      vi.advanceTimersByTime(10_500);
    });
    expect(screen.getByTestId("act").textContent).toBe("waiting");
  });
});
