import { Link } from "react-router";
import { INDEPENDENT_NOTICE, RESULT_NOTICE } from "@/i18n";
import { useSession } from "@/state/store";
import { Band, Grid12, Wrap } from "@/components/ds/Section";
import { EXPLORE_LINKS } from "./navItems";

const linkCls = "inline-flex min-h-11 items-center text-on-ink underline decoration-gold decoration-1 underline-offset-4 hover:decoration-2";

/**
 * Every page ends here, on the ink band (evening). The two notices are required on every page (PRODUCT.md, Brand Commitments):
 * the independence line, and the "rules check, not legal or medical advice" line (every page can lead to or show a result).
 */
export function Footer() {
  const { state, t } = useSession();
  const spark = import.meta.env.VITE_BUILT_WITH_SPARK === "1";
  return (
    <Band tone="ink" as="footer" pad="none" className="no-print">
      <Wrap width="wide" className="py-14 md:py-16">
        <Grid12>
          <div className="lg:col-span-5">
            <p className="m-0 font-display text-[1.5rem] font-medium">Bima Sarthi</p>
            <p className="mt-2 max-w-sm text-on-ink-soft">{t("foot_blurb")}</p>
          </div>
          <nav aria-label={t("foot_explore")} className="lg:col-span-3 lg:col-start-7">
            <p className="m-0 mb-2 font-semibold text-on-ink">{t("foot_explore")}</p>
            <ul className="m-0 list-none space-y-1 p-0">
              {EXPLORE_LINKS.map((l) => (
                <li key={l.label}>
                  <Link to={l.to} className={linkCls}>
                    {t(l.label)}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <nav aria-label={t("foot_use")} className="lg:col-span-3">
            <p className="m-0 mb-2 font-semibold text-on-ink">{t("foot_use")}</p>
            <ul className="m-0 list-none space-y-1 p-0">
              {[
                ["/check-claim", t("nav_check")],
                ["/action-plan", t("nav_action")],
                ["/help", t("nav_help")],
              ].map(([to, text]) => (
                <li key={to}>
                  <Link to={to} className={linkCls}>
                    {text}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </Grid12>
      </Wrap>
      <div className="border-t border-on-ink-soft/30">
        <Wrap width="wide" className="space-y-1 py-6 text-[0.9375rem] text-on-ink-soft">
          <p className="m-0 font-semibold text-on-ink">
            {RESULT_NOTICE}
            {state.lang === "hi" ? <span lang="hi"> {t("notice_result_hi")}</span> : null}
          </p>
          <p className="m-0">{INDEPENDENT_NOTICE}</p>
          {spark ? <p className="m-0">Built with Muse Spark Open</p> : null}
        </Wrap>
      </div>
    </Band>
  );
}
