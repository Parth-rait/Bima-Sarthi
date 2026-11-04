import { useEffect, useId, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router";
import markUrl from "@/assets/art/mark.svg";
import { Button } from "@/components/ds/Button";
import { Wrap } from "@/components/ds/Section";
import { IconChevronDown, IconMenu } from "@/components/icons";
import { HINDI_DRAFT_NOTE } from "@/i18n";
import { cn } from "@/lib/utils";
import { useSession } from "@/state/store";
import { MobileMenu } from "./MobileMenu";
import { LangToggle } from "./Seg";
import { EXPLORE_LINKS, MAIN_LINKS } from "./navItems";

const linkCls =
  "inline-flex min-h-11 items-center border-b-2 border-transparent px-3 text-[1rem] font-medium text-ink no-underline hover:border-gold aria-[current=page]:border-gold aria-[current=page]:font-bold";

/** Explore: a disclosure (button + list), not an ARIA menu. Escape and outside click close it; focus returns to the button. */
function Explore() {
  const { t } = useSession();
  const [open, setOpen] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const loc = useLocation();

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => setOpen(false), [loc.pathname, loc.hash]);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        btn.current?.focus();
      }
    };
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={wrap} className="relative">
      <button ref={btn} type="button" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen((o) => !o)} className={cn(linkCls, "cursor-pointer gap-1 bg-transparent", open && "border-gold")}>
        {t("nav_explore")}
        <IconChevronDown size={18} className={cn("transition-transform duration-150 motion-reduce:transition-none", open && "rotate-180")} />
      </button>
      <ul
        id={panelId}
        hidden={!open}
        className="absolute left-0 top-full z-[var(--z-nav)] mt-2 w-80 list-none rounded-card border border-line bg-paper p-2 text-ink shadow-lift"
      >
        {EXPLORE_LINKS.map((l) => (
          <li key={l.label}>
            <Link to={l.to} className="block rounded-ctl px-3 py-2 no-underline hover:bg-peach">
              <span className="block font-semibold text-ink">{t(l.label)}</span>
              <span className="block text-control text-ink-soft">{t(l.hint)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** True once the page has scrolled past the very top (the navbar then gets its own ground). */
function useScrolled(threshold = 12) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > threshold);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, [threshold]);
  return scrolled;
}

/**
 * Full-width bar (inner well `wide`). On the landing page it is transparent over the sky hero until you scroll
 * (the hero carries an ivory scrim at its top so ink links stay readable); everywhere else it sits on ivory with a hairline.
 */
export function Navbar() {
  const { state, t } = useSession();
  const [menu, setMenu] = useState(false);
  const menuBtn = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const loc = useLocation();
  const scrolled = useScrolled();
  const overHero = loc.pathname === "/" && !scrolled;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => setMenu(false), [loc.pathname, loc.hash]);

  return (
    <header
      data-layout="navbar"
      data-over-hero={overHero ? "true" : undefined}
      className={cn(
        "no-print sticky top-0 z-[var(--z-nav)] text-ink transition-[background-color,border-color] duration-200 motion-reduce:transition-none",
        overHero ? "border-b border-transparent bg-transparent" : "border-b border-line bg-ivory/95 backdrop-blur-sm",
      )}
    >
      <Wrap width="wide" className="flex min-h-[var(--nav-h)] items-center gap-3">
        <Link to="/" className="flex min-h-11 items-center gap-3 text-ink no-underline" aria-label={`Bima Sarthi, ${t("nav_home")}`}>
          <img src={markUrl} alt="" width={36} height={36} className="size-9" />
          <span className="font-display text-[1.375rem] font-medium tracking-tight">Bima Sarthi</span>
        </Link>
        <nav aria-label={t("nav_main")} className="ml-4 hidden items-center gap-1 lg:flex">
          {MAIN_LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} className={linkCls}>
              {t(l.label)}
            </NavLink>
          ))}
          <Explore />
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <LangToggle className="hidden sm:inline-flex" />
          <Button to="/check-claim" variant="primary" size="sm" className="hidden sm:inline-flex">
            {t("nav_check")}
          </Button>
          <button
            ref={menuBtn}
            type="button"
            aria-expanded={menu}
            aria-controls={menuId}
            aria-haspopup="dialog"
            onClick={() => setMenu(true)}
            className="inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center gap-2 rounded-ctl border border-ink bg-transparent px-3 font-medium text-ink hover:bg-peach lg:hidden"
          >
            <IconMenu size={22} />
            <span>{t("nav_menu")}</span>
          </button>
        </div>
      </Wrap>
      {state.lang === "hi" ? <p className="m-0 border-t border-line bg-ivory px-4 py-2 text-center text-control text-ink-soft">{HINDI_DRAFT_NOTE}</p> : null}
      <MobileMenu id={menuId} open={menu} onClose={() => setMenu(false)} />
    </header>
  );
}
