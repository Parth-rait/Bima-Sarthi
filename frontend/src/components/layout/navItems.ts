import type { Key } from "@/i18n";

/** Top-level links, and the Explore menu. One list, used by the navbar, the mobile menu and the footer. */
export const MAIN_LINKS: Array<{ to: string; label: Key; end?: boolean }> = [
  { to: "/", label: "nav_home", end: true },
  { to: "/about", label: "nav_about" },
  { to: "/how-it-works", label: "nav_how" },
  { to: "/cases", label: "gallery" },
  { to: "/schemes", label: "nav_schemes" },
  { to: "/help", label: "nav_help" },
];

export const EXPLORE_LINKS: Array<{ to: string; label: Key; hint: Key }> = [
  { to: "/about", label: "ex_what", hint: "ex_what_h" },
  { to: "/how-it-works", label: "ex_how", hint: "ex_how_h" },
  { to: "/cases", label: "ex_cases", hint: "ex_cases_h" },
  { to: "/evidence", label: "ex_evidence", hint: "ex_evidence_h" },
  { to: "/privacy", label: "ex_privacy", hint: "ex_privacy_h" },
  { to: "/help#faq", label: "ex_faq", hint: "ex_faq_h" },
];
