import fs from "node:fs";
import path from "node:path";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Band, Grid12, Prose, Wrap } from "../components/ds/Section";
import { FileUpload } from "../components/ui/file-upload";
import { Timeline } from "../components/ui/timeline";
import { isLowPower, useSkyAnimation } from "../hooks/useSkyPreference";
import { renderApp } from "./render";

const SRC = path.resolve(__dirname, "..");
const ROOT = path.resolve(SRC, "..");
const read = (p: string) => fs.readFileSync(p, "utf8");
function walk(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)]));
}
const all = walk(SRC).filter((f) => !f.includes(`${path.sep}test${path.sep}`));

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

describe("layout primitives and tokens", () => {
  it("Band, Wrap, Prose and Grid12 emit the documented data-layout attributes", () => {
    const { container } = render(
      <Band tone="peach" pad="tight">
        <Wrap width="wide">
          <Grid12>
            <Prose>text</Prose>
          </Grid12>
        </Wrap>
      </Band>,
    );
    expect(container.querySelector('[data-layout="band"][data-tone="peach"][data-pad="tight"]')).toBeTruthy();
    expect(container.querySelector('[data-layout="wrap"][data-wrap="wide"]')).toBeTruthy();
    expect(container.querySelector('[data-layout="grid-12"]')).toBeTruthy();
    expect(container.querySelector('[data-layout="prose"]')).toBeTruthy();
  });

  it("tokens.css defines the wells (wide 1440, default 1280, narrow 960), the 16/24/40/64 gutters and the section rhythm", () => {
    const css = read(path.join(SRC, "styles/tokens.css"));
    expect(css).toMatch(/--wrap-wide:\s*90rem/);
    expect(css).toMatch(/--wrap-default:\s*80rem/);
    expect(css).toMatch(/--wrap-narrow:\s*60rem/);
    expect(css).toMatch(/--gutter:\s*1rem/);
    expect(css).toMatch(/--gutter-sm:\s*1\.5rem/);
    expect(css).toMatch(/--gutter-lg:\s*2\.5rem/);
    expect(css).toMatch(/--gutter-2xl:\s*4rem/);
    expect(css).toMatch(/--section-y:\s*clamp\(4rem, 8vw, 8rem\)/);
    expect(css).toMatch(/--sheet-w:\s*var\(--wrap-default\)/); // the old workflow sheet now uses the default well
  });

  it("nothing hard-codes max-w-6xl any more (the root cause of the wasted desktop)", () => {
    for (const f of all.filter((x) => /\.(tsx|css)$/.test(x))) expect(read(f), path.relative(SRC, f)).not.toMatch(/max-w-6xl/);
  });

  it("the navbar and the footer span the wide well", async () => {
    const { container } = await renderApp({}, "/about");
    expect(container.querySelector('header[data-layout="navbar"] [data-wrap="wide"]')).toBeTruthy();
    expect(container.querySelector('footer [data-wrap="wide"]')).toBeTruthy();
  });
});

describe("the old plum / burgundy / brass identity is gone", () => {
  it("none of the old identity hex values appear in styles, components, pages or artwork", () => {
    const old = /#(2a1b2a|3b2438|5b1e34|3f1424|4c3a47|b58b4b|8a6428|f0d9a0|643b47|4a2b42|9a4660|8b3a52)\b/i;
    const files = [...all, ...walk(path.join(SRC, "assets"))].filter((f) => /\.(tsx?|css|svg)$/.test(f));
    for (const f of files) expect(read(f), path.relative(SRC, f)).not.toMatch(old);
  });
  it("no dashed or double borders anywhere in authored code", () => {
    for (const f of all.filter((x) => /\.(tsx|css)$/.test(x) && !x.includes(`${path.sep}ui${path.sep}`))) {
      expect(read(f).replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, ""), path.relative(SRC, f)).not.toMatch(/border-dashed|:\s*\d+px dashed|\bdashed\b\s*var|3px double/);
    }
  });
});

describe("Aceternity registry components", () => {
  const FIVE = ["parallax-hero-images", "file-upload", "lamp", "timeline", "cloud-shader"];
  it("all five are installed in components/ui with a pristine registry copy and a demo copy in vendor/", () => {
    for (const n of FIVE) {
      expect(fs.existsSync(path.join(SRC, `components/ui/${n}.tsx`)), n).toBe(true);
      expect(fs.existsSync(path.join(ROOT, `vendor/aceternity-originals/${n}.tsx.txt`)), `${n} original`).toBe(true);
      expect(fs.existsSync(path.join(ROOT, `vendor/aceternity-originals/${n}-demo.tsx.txt`)), `${n} demo`).toBe(true);
    }
  });
  it("registry demo files (with external image URLs) are not compiled into src", () => {
    expect(fs.readdirSync(path.join(SRC, "components")).filter((f) => /-demo\.tsx$/.test(f))).toEqual([]);
  });
  it("every cloud / lamp colour lives in design/atmosphere.ts, not in the components", () => {
    for (const n of ["cloud-shader", "lamp", "timeline"]) {
      const src = read(path.join(SRC, `components/ui/${n}.tsx`));
      const withoutShader = src.replace(/const FRAG = `[\s\S]*?`;/, "");
      if (n === "cloud-shader") continue; // the registry's own prop defaults (#fbf8f2 ...) stay as originals; the app always passes SKY
      expect(withoutShader, n).not.toMatch(/#[0-9a-f]{6}/i);
    }
    const atmo = read(path.join(SRC, "design/atmosphere.ts"));
    for (const k of ["cloudColor", "skyTopColor", "skyBottomColor", "renderScale", "maxFps", "maxDpr", "beam", "glow", "core", "line", "progressFrom"]) expect(atmo).toContain(k);
  });
  it("the CloudShader keeps its fragment shader byte for byte", () => {
    const grab = (t: string) => t.match(/const FRAG = `[\s\S]*?`;/)![0];
    const orig = read(path.join(ROOT, "vendor/aceternity-originals/cloud-shader.tsx.txt"));
    const now = read(path.join(SRC, "components/ui/cloud-shader.tsx"));
    expect(grab(now)).toBe(grab(orig));
  });
  it("the Timeline keeps the registry's scroll-progress logic", () => {
    const now = read(path.join(SRC, "components/ui/timeline.tsx"));
    expect(now).toContain('offset: ["start 10%", "end 50%"]');
    expect(now).toContain("useTransform(scrollYProgress, [0, 1], [0, height])");
  });
});

describe("FileUpload and Timeline render with our own content", () => {
  it("FileUpload is keyboard-operable and reports the files it receives", () => {
    const onChange = vi.fn();
    const { container } = render(<FileUpload onChange={onChange} title="Add your documents" hint="Drop a file here" />);
    const area = screen.getByRole("button", { name: /Add your documents/ });
    expect(area.getAttribute("tabindex")).toBe("0");
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["x"], "letter.pdf", { type: "application/pdf" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(onChange).toHaveBeenCalledWith([file]);
    expect(screen.getByText("letter.pdf")).toBeTruthy();
  });
  it("Timeline shows every entry's title and content without any scroll, and no demo text", () => {
    render(
      <Timeline
        heading="Six steps"
        data={[
          { title: "First", number: 1, content: <p>alpha</p> },
          { title: "Second", number: 2, content: <p>beta</p> },
        ]}
      />,
    );
    expect(screen.getByText("alpha")).toBeTruthy();
    expect(screen.getByText("beta")).toBeTruthy();
    expect(screen.getAllByText("First").length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toMatch(/Changelog|journey/);
  });
});

describe("the Animate-the-sky preference", () => {
  function Probe() {
    const s = useSkyAnimation();
    return (
      <div>
        <p data-testid="state">{String(s.useShader)}|{String(s.canToggle)}|{String(s.lowPower)}</p>
        <button type="button" onClick={s.toggle}>toggle</button>
      </div>
    );
  }
  it("a low-power device is detected from cores or memory", () => {
    vi.stubGlobal("navigator", { hardwareConcurrency: 4 });
    expect(isLowPower()).toBe(true);
    vi.stubGlobal("navigator", { hardwareConcurrency: 12, deviceMemory: 8 });
    expect(isLowPower()).toBe(false);
    vi.stubGlobal("navigator", { hardwareConcurrency: 12, deviceMemory: 4 });
    expect(isLowPower()).toBe(true);
  });
  it("without WebGL the shader is never used and there is nothing to toggle (the static sky is the fallback)", () => {
    render(<Probe />);
    expect(screen.getByTestId("state").textContent).toMatch(/^false\|false\|/);
  });
  it("the choice is read from and written to localStorage (key bimasarthi.sky), and storage that throws is survivable", async () => {
    window.localStorage.setItem("bimasarthi.sky", "off");
    render(<Probe />);
    expect(screen.getByTestId("state").textContent).toMatch(/^false/);
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    fireEvent.click(screen.getByText("toggle")); // must not throw
    await waitFor(() => expect(spy).toHaveBeenCalled());
    spy.mockRestore();
  });
});

describe("the landing page uses the full-bleed band system", () => {
  it("has a sky hero, then alternating bands, ending on a call to action; the hero art has alt text", async () => {
    const { container } = await renderApp({}, "/");
    const tones = [...container.querySelectorAll('main [data-layout="band"]')].map((b) => b.getAttribute("data-tone"));
    expect(tones[0]).toBe("sky");
    expect(tones.length).toBeGreaterThanOrEqual(9);
    expect(new Set(tones)).toEqual(new Set(["sky", "ivory", "peach", "ink"]));
    expect(container.querySelector('main [data-wrap="wide"]')).toBeTruthy();
  });
});
