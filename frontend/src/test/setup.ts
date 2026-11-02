import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => cleanup());

// jsdom lacks these.
if (typeof window !== "undefined") {
  window.scrollTo = (() => {}) as typeof window.scrollTo;
  if (!window.matchMedia) {
    window.matchMedia = ((q: string) => ({
      matches: false,
      media: q,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
      dispatchEvent: () => false,
      onchange: null,
    })) as typeof window.matchMedia;
  }
  Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || (() => {});
  // jsdom has no ResizeObserver; the installed glass component uses one.
  if (!("ResizeObserver" in window)) {
    (window as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }
  // jsdom has no IntersectionObserver; motion's whileInView (Lamp) and the CloudShader pause logic use it.
  if (!("IntersectionObserver" in window)) {
    (window as unknown as { IntersectionObserver: unknown }).IntersectionObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
      takeRecords() {
        return [];
      }
    };
  }
}
