import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { Accordion } from "../components/ds/Accordion";
import { Button } from "../components/ds/Button";
import { FileUploader, formatSize, isAccepted, overLimit } from "../components/ds/FileUploader";
import { Modal } from "../components/ds/Modal";
import { ProgressIndicator } from "../components/ds/ProgressIndicator";
import { StatusBadge } from "../components/ds/StatusBadge";
import { Stepper } from "../components/ds/Stepper";
import { ToastProvider, useToast } from "../components/ds/Toast";
import { ArtworkImage } from "../components/landing/ArtworkImage";
import { initialState, reducer } from "../state/session";
import { check } from "./fixtures";
import { renderIn } from "./render";

const f = (name: string, size = 10, type = "image/png") => {
  const file = new File(["x"], name, { type });
  Object.defineProperty(file, "size", { value: size });
  return file;
};

function Uploader({ initial = [] as File[] }) {
  const [files, setFiles] = useState<File[]>(initial);
  return <FileUploader files={files} onChange={setFiles} label="Choose files or take a photo" inputId="files" />;
}
const pick = (files: File[]) => fireEvent.change(document.getElementById("files")!, { target: { files } });

describe("FileUploader", () => {
  it("accepts exactly what the backend accepts: JPG, PNG, PDF (by extension or type)", () => {
    expect(["a.jpg", "a.JPEG", "a.png", "a.pdf"].every((n) => isAccepted(f(n, 1, "")))).toBe(true);
    expect(isAccepted(f("a.txt", 1, "text/plain"))).toBe(false);
    expect(isAccepted(f("a.heic", 1, "image/heic"))).toBe(false);
    expect(isAccepted(f("scan", 1, "application/pdf"))).toBe(true);
    const input = document.createElement("input");
    renderIn(<Uploader />);
    const el = document.getElementById("files") as HTMLInputElement;
    expect(el.accept).toMatch(/\.jpg.*\.png.*\.pdf/);
    expect(el.multiple).toBe(true);
    expect(input).toBeTruthy();
  });

  it("rejects an unsupported file with what happened and what to do, and keeps the valid ones", () => {
    renderIn(<Uploader />);
    pick([f("notes.txt", 5, "text/plain"), f("letter.png")]);
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("notes.txt is not a JPG, PNG or PDF, so it was not added.");
    expect(alert.textContent).toContain("Choose a JPG, PNG or PDF file, or take a photo of the page.");
    expect(document.querySelectorAll(".fname")).toHaveLength(1);
    expect(document.querySelector(".fname")!.textContent).toBe("letter.png");
  });

  it("rejects an empty file", () => {
    renderIn(<Uploader />);
    pick([f("empty.pdf", 0, "application/pdf")]);
    expect(screen.getByRole("alert").textContent).toContain("is empty");
  });

  it("lists size and a preview slot, and removes or replaces a file", () => {
    renderIn(<Uploader initial={[f("a.png", 2048), f("b.pdf", 1024 * 1024 * 3, "application/pdf")]} />);
    expect(screen.getByText("2 KB")).toBeTruthy();
    expect(screen.getByText("3.0 MB")).toBeTruthy();
    // replace b.pdf with c.png through the hidden single-file input
    const swapInput = document.querySelector('input[aria-hidden="true"]') as HTMLInputElement;
    fireEvent.click(screen.getByRole("button", { name: /Replace b\.pdf/ }));
    fireEvent.change(swapInput, { target: { files: [f("c.png", 100)] } });
    expect([...document.querySelectorAll(".fname")].map((n) => n.textContent)).toEqual(["a.png", "c.png"]);
    fireEvent.click(screen.getByRole("button", { name: /Remove a\.png/ }));
    expect([...document.querySelectorAll(".fname")].map((n) => n.textContent)).toEqual(["c.png"]);
  });

  it("shows the share of the 25 MB allowance used as a real measurement, and flags going over", () => {
    renderIn(<Uploader initial={[f("a.pdf", 10 * 1024 * 1024, "application/pdf")]} />);
    const bar = screen.getByRole("progressbar", { name: "Upload allowance" });
    expect(Number(bar.getAttribute("aria-valuenow"))).toBeCloseTo(40, 0);
    expect(overLimit([f("a.pdf", 26 * 1024 * 1024)])).toBe(true);
    expect(formatSize(26 * 1024 * 1024)).toBe("26.0 MB");
    renderIn(<Uploader initial={[f("big.pdf", 26 * 1024 * 1024, "application/pdf")]} />);
    expect(screen.getAllByRole("alert").some((a) => /over|more than 25 MB/.test(a.textContent!) || a.textContent!.includes("25 MB"))).toBe(true);
  });

  it("offers camera capture and says nothing is sent until the read button is pressed", () => {
    renderIn(<Uploader />);
    expect((document.querySelector('input[capture="environment"]') as HTMLInputElement).accept).toBe("image/*");
    expect(screen.getByText("Take a photo")).toBeTruthy();
    expect(document.body.textContent).toContain("Nothing is sent until you press the read button.");
  });

  it("never shows a fake upload percentage", () => {
    renderIn(<Uploader initial={[f("a.png", 5)]} />);
    expect(document.body.textContent).not.toMatch(/\d+\s?% (uploaded|complete|done)/i);
  });

  it("is operable from the keyboard: the file inputs are real inputs with labels", () => {
    renderIn(<Uploader />);
    const input = document.getElementById("files") as HTMLInputElement;
    expect(input.type).toBe("file");
    expect(document.querySelector(`label[for="files"]`)!.textContent).toContain("Choose files");
  });
});

describe("ProgressIndicator", () => {
  it("is determinate only when given a value (no fake progress)", () => {
    const { rerender } = render(<ProgressIndicator label="x" />);
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBeNull();
    rerender(<ProgressIndicator label="x" value={250} />);
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("100");
  });
});

describe("Button", () => {
  it("loading disables the button, sets aria-busy and keeps the label", () => {
    render(<Button loading>Save</Button>);
    const b = screen.getByRole("button", { name: /Save/ });
    expect(b).toHaveProperty("disabled", true);
    expect(b.getAttribute("aria-busy")).toBe("true");
  });
  it("renders a link for `to` and an anchor for `href`, with a 44px minimum height class", () => {
    render(
      <MemoryRouter>
        <Button to="/x">Go</Button>
        <Button href="https://example.org/">Out</Button>
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Go" }).getAttribute("href")).toBe("/x");
    expect(screen.getByRole("link", { name: "Out" }).className).toContain("min-h-11");
  });
  it("is type=button by default so it never submits a form by accident", () => {
    render(<Button>Hi</Button>);
    expect(screen.getByRole("button").getAttribute("type")).toBe("button");
  });
});

describe("Modal", () => {
  function Host() {
    const [open, setOpen] = useState(false);
    return (
      <>
        <button onClick={() => setOpen(true)}>open</button>
        <Modal open={open} onClose={() => setOpen(false)} title="Sure?" description="It cannot be undone." closeLabel="Close">
          <button data-autofocus>keep</button>
          <button>delete</button>
        </Modal>
      </>
    );
  }
  it("is a labelled, described modal dialog; focus goes to the safe action; Escape closes and returns focus", () => {
    render(<Host />);
    const opener = screen.getByText("open");
    opener.focus();
    fireEvent.click(opener);
    const d = screen.getByRole("dialog", { name: "Sure?" });
    expect(d.getAttribute("aria-modal")).toBe("true");
    expect(d.getAttribute("aria-describedby")).toBeTruthy();
    expect(document.activeElement).toBe(within(d).getByText("keep"));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(opener);
  });
});

describe("Accordion", () => {
  it("multiple=false keeps one panel open", () => {
    render(<Accordion multiple={false} items={[{ id: "a", title: "A", content: "aa" }, { id: "b", title: "B", content: "bb" }]} />);
    fireEvent.click(screen.getByRole("button", { name: "A" }));
    fireEvent.click(screen.getByRole("button", { name: "B" }));
    expect(screen.getByRole("button", { name: "A" }).getAttribute("aria-expanded")).toBe("false");
    expect(screen.getByRole("button", { name: "B" }).getAttribute("aria-expanded")).toBe("true");
  });
});

describe("Stepper", () => {
  it("marks the current step with aria-current and finished steps with a tick, not colour alone", () => {
    render(<Stepper label="Steps" current="confirm" steps={[{ id: "upload", text: "1. Upload" }, { id: "confirm", text: "2. Confirm" }, { id: "result", text: "3. Result" }]} />);
    const items = screen.getAllByRole("listitem");
    expect(items[1].getAttribute("aria-current")).toBe("step");
    expect(items[0].querySelector("svg")).toBeTruthy();
    expect(items[2].getAttribute("data-state")).toBe("todo");
  });
});

describe("Toast", () => {
  it("announces politely and can be dismissed", () => {
    function Push() {
      const { push } = useToast();
      return <button onClick={() => push("Saved")}>go</button>;
    }
    render(
      <ToastProvider closeLabel="Close">
        <Push />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByText("go"));
    const region = screen.getByRole("status");
    expect(region.getAttribute("aria-live")).toBe("polite");
    expect(region.textContent).toContain("Saved");
    fireEvent.click(within(region).getByRole("button", { name: "Close" }));
    expect(region.textContent).not.toContain("Saved");
  });
});

describe("StatusBadge", () => {
  it("shows the word AND a shape for each verdict (never colour alone)", () => {
    for (const [v, word] of [["CHALLENGEABLE", "Challengeable"], ["NEED_INFO", "Need info"], ["CONSISTENT", "Consistent"]] as const) {
      const { container, unmount } = renderIn(<StatusBadge verdict={v} />);
      expect(container.textContent).toBe(word);
      expect(container.querySelector("svg")).toBeTruthy();
      unmount();
    }
  });
});

describe("ArtworkImage", () => {
  it("falls back to the plain image with alt text where WebGL does not exist", () => {
    render(<ArtworkImage src="/x.svg" alt="Dossier artwork" />);
    expect(screen.getByAltText("Dossier artwork").tagName).toBe("IMG");
    expect(document.querySelector("canvas")).toBeNull();
  });
  it("is the plain image under reduced motion even if WebGL existed", () => {
    vi.stubGlobal("matchMedia", (q: string) => ({ matches: /reduce/.test(q), media: q, addEventListener() {}, removeEventListener() {} }));
    render(<ArtworkImage src="/x.svg" alt="Plain" />);
    expect(screen.getByAltText("Plain")).toBeTruthy();
    expect(document.querySelector("canvas")).toBeNull();
    vi.unstubAllGlobals();
  });
});

describe("session reducer: report id and checklist ticks", () => {
  const base = initialState({ sid: "server-session", view: "confirm" });
  it("creates a report id on the first check, keeps it on a re-check, and never uses the session id", () => {
    const s1 = reducer(base, { type: "checked", check: check(), reportId: "r-1" });
    expect(s1.reportId).toBe("r-1");
    expect(s1.reportId).not.toBe(s1.sid);
    const s2 = reducer(reducer(s1, { type: "toggle_item", id: "doc-0" }), { type: "checked", check: check(), reportId: "r-2" });
    expect(s2.reportId).toBe("r-1");
    expect(s2.checkedItems).toEqual({ "doc-0": true });
  });
  it("a new extraction, manual entry or reset clears the report and the ticks", () => {
    const s1 = reducer(reducer(base, { type: "checked", check: check(), reportId: "r-1" }), { type: "toggle_item", id: "x" });
    for (const next of [
      reducer(s1, { type: "extracted", facts: {}, pages: 1, backend: null, hint: null }),
      reducer(s1, { type: "manual" }),
      reducer(s1, { type: "reset", view: "upload" }),
    ]) {
      expect(next.reportId).toBeNull();
      expect(next.checkedItems).toEqual({});
    }
  });
  it("toggling twice unticks", () => {
    const s = reducer(reducer(base, { type: "toggle_item", id: "a" }), { type: "toggle_item", id: "a" });
    expect(s.checkedItems.a).toBe(false);
  });
});

describe("waitFor sanity", () => {
  it("jsdom has no WebGL (so the lazy chromatic chunk is never mounted in tests)", async () => {
    await waitFor(() => expect("WebGLRenderingContext" in window).toBe(false));
  });
});
