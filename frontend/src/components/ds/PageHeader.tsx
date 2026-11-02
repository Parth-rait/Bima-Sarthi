import type { ReactNode } from "react";
import { useSession } from "@/state/store";
import { Band, Grid12, Wrap } from "./Section";

/**
 * The top of every editorial page: the page's one <h1> (it receives focus on navigation), a lead, optional artwork.
 * A full-bleed peach-to-ivory band; the wide well is split in a 12-column grid (7 / 5) so the title is never boxed in a narrow column.
 */
export function PageHeader({ title, lead, art, children }: { title: string; lead?: ReactNode; art?: ReactNode; children?: ReactNode }) {
  const { state, t } = useSession();
  return (
    <Band tone="peach" pad="tight" as="header" className="bg-[linear-gradient(180deg,var(--color-sky-pale)_0%,var(--color-peach)_100%)]">
      <Wrap width="wide">
        <Grid12 className="items-center">
          <div className={art ? "lg:col-span-7" : "lg:col-span-9"}>
            <h1 tabIndex={-1} data-page-heading className="m-0 max-w-[26ch] font-display text-h1 font-medium text-ink">
              {title}
            </h1>
            {lead ? <p className="mt-5 max-w-[68ch] text-lead text-ink">{lead}</p> : null}
            {state.lang === "hi" ? (
              <p role="note" className="mt-4 max-w-[68ch] rounded-ctl bg-ivory/70 px-3 py-2 text-[0.9375rem] text-ink-soft">
                {t("editorial_note")}
              </p>
            ) : null}
            {children}
          </div>
          {art ? <div className="hidden lg:col-span-4 lg:col-start-9 lg:block">{art}</div> : null}
        </Grid12>
      </Wrap>
    </Band>
  );
}
