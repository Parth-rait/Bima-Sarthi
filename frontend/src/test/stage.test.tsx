import fs from "node:fs";
import path from "node:path";
import { act, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkStage, type StageStep } from "../components/stage/WorkStage";
import { renderIn } from "./render";

const STEPS: StageStep[] = [
  { id: "facts", label: "stage_saving", mode: "saving" },
  { id: "check", label: "stage_checking", mode: "checking" },
];
const SRC = path.resolve(__dirname, "..");

afterEach(() => vi.useRealTimers());

describe("the work stage (claim flow, while a request is in flight)", () => {
  it("names the request in flight and marks the steps before it done, in words and not by colour alone", () => {
    renderIn(<WorkStage steps={STEPS} current="check" slow={false} />);
    const list = screen.getByRole("list", { name: "What is happening now" });
    const items = within(list).getAllByRole("listitem");
    expect(items[0].textContent).toContain("Saving your answers, done");
    expect(items[1].getAttribute("aria-current")).toBe("step");
    expect(items[1].textContent).toContain("Checking them against the rules, in progress");
    expect(document.querySelector(".stage-now")!.textContent).toBe("Checking them against the rules");
  });

  it("counts real seconds, and says so when the server is slow", () => {
    vi.useFakeTimers();
    const { unmount } = renderIn(<WorkStage steps={STEPS} current="facts" slow={false} />);
    expect(document.querySelector(".stage-secs")!.textContent).toBe("0");
    act(() => vi.advanceTimersByTime(3000));
    expect(document.querySelector(".stage-secs")!.textContent).toBe("3");
    expect(document.querySelector(".stage-slow")).toBeNull();
    unmount();
    renderIn(<WorkStage steps={STEPS} current="facts" slow />);
    expect(document.querySelector(".stage-slow")).toBeTruthy();
  });

  it("without WebGL it is the CSS file only: no canvas, no three.js chunk, the picture hidden from assistive tech", () => {
    renderIn(<WorkStage steps={STEPS} current="facts" slow={false} />);
    expect(document.querySelector("canvas")).toBeNull();
    expect(document.querySelector(".stage-css")).toBeTruthy();
    expect(document.querySelector(".stage-viz")!.getAttribute("aria-hidden")).toBe("true");
    // the drag hint is only for a real interactive scene
    expect(screen.queryByText(/Drag the pages/)).toBeNull();
  });

  it("is not a second live region (the screen's own status line announces the work once)", () => {
    renderIn(<WorkStage steps={STEPS} current="facts" slow={false} />);
    expect(document.querySelector(".stage [aria-live], .stage[role='status']")).toBeNull();
  });

  it("three.js is reached only through the lazy stage chunk, and the scene keeps its colours in atmosphere.ts", () => {
    const importers: string[] = [];
    const walk = (d: string) => {
      for (const f of fs.readdirSync(d)) {
        const p = path.join(d, f);
        if (fs.statSync(p).isDirectory()) walk(p);
        else if (/\.tsx?$/.test(f) && !p.includes(`${path.sep}test${path.sep}`) && /from "(three|@react-three\/[^"]+)"/.test(fs.readFileSync(p, "utf8"))) importers.push(path.relative(SRC, p));
      }
    };
    walk(SRC);
    expect(importers).toEqual([path.join("components", "stage", "ClaimScene.tsx")]);
    const stage = fs.readFileSync(path.join(SRC, "components/stage/WorkStage.tsx"), "utf8");
    expect(stage).toMatch(/lazy\(loadScene\)/);
    expect(stage).not.toMatch(/^import (?!type ).*ClaimScene";$/m);
    const scene = fs.readFileSync(path.join(SRC, "components/stage/ClaimScene.tsx"), "utf8");
    expect(scene.replace(/color="#ffffff"/g, "")).not.toMatch(/#[0-9a-f]{6}/i);
  });
});
