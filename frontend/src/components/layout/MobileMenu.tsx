import { useRef } from "react";
import { createPortal } from "react-dom";
import { Link, NavLink } from "react-router";
import { Button } from "@/components/ds/Button";
import { Wrap } from "@/components/ds/Section";
import { IconX } from "@/components/icons";
import { useFocusTrap } from "@/hooks/useFocusTrap";
import { useSession } from "@/state/store";
import { LangToggle, RoleToggle } from "./Seg";
import { EXPLORE_LINKS, MAIN_LINKS } from "./navItems";

/**
 * Full-screen menu for phones and tablets: a modal dialog (focus trapped, Escape and the close button dismiss it,
 * page scroll locked, focus returns to the Menu button). Rendered only while open, so its controls never duplicate
 * the desktop bar's in the accessibility tree.
 */
export function MobileMenu({ id, open, onClose }: { id: string; open: boolean; onClose: () => void }) {
  const { t } = useSession();
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, open, onClose);
  if (!open) return null;
  const item = "flex min-h-12 items-center border-b border-line py-2 text-[1.125rem] text-ink no-underline";
  return createPortal(
    <div
      id={id}
      ref={ref}
      role="dialog"
      aria-modal="true"
      aria-label={t("nav_mobile")}
      tabIndex={-1}
      className="no-print fixed inset-0 z-[65] overflow-y-auto bg-ivory text-ink"
    >
      <Wrap width="wide" className="flex min-h-[var(--nav-h)] items-center justify-between">
        <Link to="/" onClick={onClose} className="font-display text-[1.375rem] text-ink no-underline">
          Bima Sarthi
        </Link>
        <button type="button" data-autofocus onClick={onClose} aria-label={t("nav_close")} className="inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center gap-2 rounded-ctl border border-ink bg-transparent px-3 font-medium text-ink hover:bg-peach">
          <IconX size={22} />
          <span>{t("nav_close")}</span>
        </button>
      </Wrap>
      <div className="mx-auto max-w-xl px-4 pb-10 pt-4">
        <nav aria-label={t("nav_main")}>
          <ul className="m-0 list-none p-0">
            {MAIN_LINKS.map((l) => (
              <li key={l.to}>
                <NavLink to={l.to} end={l.end} onClick={onClose} className={`${item} aria-[current=page]:font-bold aria-[current=page]:underline aria-[current=page]:decoration-gold aria-[current=page]:decoration-2 aria-[current=page]:underline-offset-8`}>
                  {t(l.label)}
                </NavLink>
              </li>
            ))}
          </ul>
          <p className="mb-1 mt-6 text-[0.9375rem] font-semibold text-ink-soft">{t("nav_explore")}</p>
          <ul className="m-0 list-none p-0">
            {EXPLORE_LINKS.map((l) => (
              <li key={l.label}>
                <Link to={l.to} onClick={onClose} className={item}>
                  {t(l.label)}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="mt-8 flex flex-col items-start gap-4">
          <LangToggle idPrefix="m-" />
          <RoleToggle idPrefix="m-" tone="light" />
          <Button to="/check-claim" variant="primary" size="lg" onClick={onClose} block>
            {t("nav_check")}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
