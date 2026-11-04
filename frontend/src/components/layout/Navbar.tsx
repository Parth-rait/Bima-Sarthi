import { useEffect, useId, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { Spark } from "@/components/ds/Spark";
import { Link, NavLink, useLocation } from "react-router";
import { motion, useReducedMotion, useScroll, useSpring } from "motion/react";
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
  "relative isolate inline-flex min-h-11 items-center rounded-full px-3.5 text-[1rem] font-medium text-ink no-underline transition-colors duration-150 aria-[current=page]:font-bold motion-reduce:transition-none";

const PILL = { type: "spring", stiffness: 420, damping: 34, mass: 0.7 } as const;

/** The glass pill behind a nav link: one shared element (layoutId) that glides from link to link as the pointer moves. */
function HoverPill() {
  const reduce = useReducedMotion();
  return (
    <motion.span
      layoutId="nav-hover"
      aria-hidden="true"
      transition={reduce ? { duration: 0 } : PILL}
      className="absolute inset-0 -z-10 rounded-full border border-white/80 bg-white/60 shadow-[inset_0_1px_0_rgb(255_255_255/0.9),0_6px_16px_-10px_rgb(52_49_138/0.45)]"
    />
  );
}

/** The current page: a saffron bead under the label, sliding to the new page on navigation. */
function CurrentBead() {
  const reduce = useReducedMotion();
  return (
    <motion.span
      layoutId="nav-current"
      aria-hidden="true"
      transition={reduce ? { duration: 0 } : PILL}
      className="absolute bottom-1 left-1/2 -z-10 h-[3px] w-5 -translate-x-1/2 rounded-full bg-linear-to-r from-apricot to-dusty-rose"
    />
  );
}

/**
 * The mark, with a little depth: it leans toward the pointer and a band of light crosses it on every page change.
 * The tilt is pointer-only decoration; under reduced motion the mark is still.
 */
function useBrandMark() {
  const loc = useLocation();
  const reduce = useReducedMotion();
  const tile = useRef<HTMLSpanElement>(null);
  const lean = (e: ReactPointerEvent<HTMLElement>) => {
    const el = tile.current;
    if (!el || reduce || e.pointerType !== "mouse") return;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - (r.left + r.width / 2)) / 60;
    const y = (e.clientY - (r.top + r.height / 2)) / 60;
    el.style.setProperty("--tilt-x", `${(-y * 14).toFixed(2)}deg`);
    el.style.setProperty("--tilt-y", `${(x * 14).toFixed(2)}deg`);
  };
  const rest = () => {
    tile.current?.style.setProperty("--tilt-x", "0deg");
    tile.current?.style.setProperty("--tilt-y", "0deg");
  };
  return { lean, rest, el: (
    <span ref={tile} className="brand-tile" aria-hidden="true">
      <img src={markUrl} alt="" width={40} height={40} className="size-10" />
      {reduce ? null : <span key={loc.pathname} className="brand-sheen" />}
    </span>
  ) };
}

/** A hairline that fills with the scroll position of the page (decoration: the scrollbar is the real control). */
function ScrollLine() {
  const { scrollYProgress } = useScroll();
  const reduce = useReducedMotion();
  const x = useSpring(scrollYProgress, { stiffness: 180, damping: 30, mass: 0.3 });
  return (
    <motion.span
      aria-hidden="true"
      style={{ scaleX: reduce ? scrollYProgress : x }}
      className="pointer-events-none absolute inset-x-0 bottom-0 h-0.5 origin-left bg-linear-to-r from-apricot via-dusty-rose to-action"
    />
  );
}

/** Explore: a disclosure (button + list), not an ARIA menu. Escape and outside click close it; focus returns to the button. */
function Explore() {
  const { t } = useSession();
  const [open, setOpen] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const loc = useLocation();
  const [hover, setHover] = useState(false);

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
      <button
        ref={btn}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
        onPointerEnter={() => setHover(true)}
        onPointerLeave={() => setHover(false)}
        className={cn(linkCls, "cursor-pointer gap-1 bg-transparent")}
      >
        {hover || open ? <HoverPill /> : null}
        {t("nav_explore")}
        <IconChevronDown size={18} className={cn("transition-transform duration-150 motion-reduce:transition-none", open && "rotate-180")} />
      </button>
      <ul
        id={panelId}
        hidden={!open}
        className="absolute left-0 top-full z-[var(--z-nav)] mt-3 w-80 list-none rounded-[1.25rem] border border-white/80 bg-paper p-2 text-ink shadow-lift"
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
 * Full-width bar (inner well `wide`). Once the page scrolls it lifts into a floating glass capsule (navbar-shell in
 * layout.css) with a scroll hairline along its foot. On the landing page it is transparent over the sky hero until you scroll
 * (the hero carries an ivory scrim at its top so ink links stay readable); everywhere else it sits on ivory with a hairline.
 */
export function Navbar() {
  const { state, t } = useSession();
  const [menu, setMenu] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);
  const menuBtn = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const loc = useLocation();
  const scrolled = useScrolled();
  const overHero = loc.pathname === "/" && !scrolled;
  const brand = useBrandMark();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => setMenu(false), [loc.pathname, loc.hash]);

  return (
    <header
      data-layout="navbar"
      data-over-hero={overHero ? "true" : undefined}
      data-floating={scrolled ? "true" : undefined}
      className={cn(
        "navbar no-print sticky top-0 z-[var(--z-nav)] text-ink",
        overHero ? "bg-transparent" : scrolled ? "bg-transparent" : "border-b border-line bg-ivory/90 backdrop-blur-md",
      )}
    >
      <div className="navbar-shell">
        <Wrap width="wide" className="relative flex min-h-[var(--nav-bar-h)] items-center gap-3">
          <Link
            to="/"
            className="brand-link flex min-h-11 items-center gap-3 text-ink no-underline"
            aria-label={`Bima Sarthi, ${t("nav_home")}`}
            onPointerMove={brand.lean}
            onPointerLeave={brand.rest}
          >
            {brand.el}
            <span className="font-display text-[1.375rem] font-medium tracking-tight">Bima Sarthi</span>
          </Link>
          <nav aria-label={t("nav_main")} className="ml-4 hidden items-center gap-0.5 lg:flex" onPointerLeave={() => setHovered(null)}>
            {MAIN_LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end} className={linkCls} onPointerEnter={() => setHovered(l.to)} onFocus={() => setHovered(l.to)} onBlur={() => setHovered(null)}>
                {({ isActive }) => (
                  <>
                    {hovered === l.to ? <HoverPill /> : null}
                    {isActive ? <CurrentBead /> : null}
                    {t(l.label)}
                  </>
                )}
              </NavLink>
            ))}
            <Explore />
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <LangToggle className="hidden sm:inline-flex" />
            <Spark className="spark-pill spark-sm hidden sm:inline-flex">
              <Button to="/check-claim" variant="primary" size="sm" className="rounded-full">
                {t("nav_check")}
              </Button>
            </Spark>
            <button
              ref={menuBtn}
              type="button"
              aria-expanded={menu}
              aria-controls={menuId}
              aria-haspopup="dialog"
              onClick={() => setMenu(true)}
              className="inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center gap-2 rounded-full border border-ink/80 bg-white/40 px-3.5 font-medium text-ink hover:bg-white/80 lg:hidden"
            >
              <IconMenu size={22} />
              <span>{t("nav_menu")}</span>
            </button>
          </div>
          {overHero ? null : <ScrollLine />}
        </Wrap>
      </div>
      {state.lang === "hi" ? <p className="m-0 border-t border-line bg-ivory px-4 py-2 text-center text-control text-ink-soft">{HINDI_DRAFT_NOTE}</p> : null}
      <MobileMenu id={menuId} open={menu} onClose={() => setMenu(false)} />
    </header>
  );
}
