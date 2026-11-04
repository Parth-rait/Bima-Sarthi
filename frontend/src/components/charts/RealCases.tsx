import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { api, type GalleryList, type GalleryListItem } from "@/api";
import { GROUND_LABEL, type Key } from "@/i18n";
import { useSession } from "@/state/store";
import { isoToDisplay } from "@/lib/dates";
import { cn } from "@/lib/utils";

/**
 * Grouped by who won, never by the raw disposal word: a forum that "dismisses" the insurer's appeal
 * is a policyholder win, so "dismissed" alone would show a win as a loss.
 */
export const WINNERS = ["policyholder", "insurer", "unknown"] as const;
export type Winner = (typeof WINNERS)[number];

export const winnerOf = (c: { policyholder_prevailed?: boolean | null }): Winner =>
  c.policyholder_prevailed === true ? "policyholder" : c.policyholder_prevailed === false ? "insurer" : "unknown";

// Neutral on purpose: sage and terracotta mean verdicts on this page, so "who won" uses ink weight instead
// (solid ink = policyholder, outlined = insurer). Every pair is ink/ivory or ink/paper (13.7:1 or better).
const SEGMENT: Record<Winner, string> = {
  policyholder: "bg-ink text-on-ink",
  insurer: "border-2 border-ink bg-paper text-ink",
  unknown: "border border-line-strong bg-ivory text-ink-soft",
};
const SWATCH: Record<Winner, string> = { policyholder: "bg-ink", insurer: "border-2 border-ink bg-paper", unknown: "border border-line-strong bg-ivory" };
const TAG: Record<Winner, string> = {
  policyholder: "bg-ink text-on-ink",
  insurer: "border border-ink bg-paper text-ink",
  unknown: "border border-line-strong text-ink-soft",
};

/** Who won one case, in the same neutral vocabulary as the bar. */
export function WinnerBadge({ prevailed }: { prevailed: boolean | null | undefined }) {
  const { t } = useSession();
  const w = winnerOf({ policyholder_prevailed: prevailed });
  return (
    <span data-winner={w} className={cn("inline-flex rounded-ctl px-2 py-0.5 text-[0.8125rem] font-semibold", TAG[w])}>
      {t(`won_${w}` as Key)}
    </span>
  );
}

let galleryCache: Promise<GalleryList> | null = null;
function loadGallery(): Promise<GalleryList> {
  galleryCache ??= api.gallery().catch((e) => {
    galleryCache = null; // a failed load may be retried on the next mount
    throw e;
  });
  return galleryCache;
}

/** Test hook: forget the cached gallery list. */
export function resetGalleryCache() {
  galleryCache = null;
}

export interface SimilarCases {
  loading: boolean;
  failed: boolean;
  cases: GalleryListItem[];
  counts: Record<Winner, number>;
}

/** The reviewed real cases whose stated rejection reason is the user's. One fetch per page load. */
export function useSimilarCases(ground: string | null): SimilarCases {
  const [list, setList] = useState<GalleryList | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!ground) return;
    let live = true;
    loadGallery()
      .then((g) => live && setList(g))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [ground]);
  return useMemo(() => {
    const cases = list && ground ? list.cases.filter((c) => c.rejection_ground === ground) : [];
    const counts = { policyholder: 0, insurer: 0, unknown: 0 } as Record<Winner, number>;
    cases.forEach((c) => (counts[winnerOf(c)] += 1));
    return { loading: !!ground && !list && !failed, failed, cases, counts };
  }, [list, ground, failed]);
}

const caseTitle = (c: GalleryListItem) => [c.citation.forum, isoToDisplay(c.citation.decided_on)].filter(Boolean).join(", ");

/** Fill `{name}` placeholders in a translated sentence. */
export const fill = (s: string, vals: Record<string, string | number>) => s.replace(/\{(\w+)\}/g, (m, k) => (k in vals ? String(vals[k]) : m));

/**
 * Real, cited consumer judgments with the same stated reason as the user's claim, drawn from the
 * reviewed case base, never from the user's own documents. The counts are small (a handful of cases),
 * so the form is a headline number and one segmented bar, not a plotted chart; every case is listed.
 */
export function RealCases({ ground }: { ground: string | null }) {
  const { state, t } = useSession();
  const { failed, loading, cases, counts } = useSimilarCases(ground);
  if (!ground) return null;
  if (!loading && !failed && cases.length === 0) return null;

  const groundLabel = (GROUND_LABEL[state.lang] as Record<string, string>)[ground] ?? ground;
  const label = (w: Winner) => t(`won_${w}` as Key);
  const total = cases.length;
  const shown = WINNERS.filter((w) => counts[w] > 0);

  return (
    <section id="real-cases" aria-labelledby="h-cases" className="scroll-mt-24 border-t border-line-strong pt-7">
      <h3 id="h-cases" className="m-0 font-display text-h2 font-medium text-ink">
        {t("rcases_h")}
      </h3>
      <p className="mb-0 mt-2 max-w-[62ch] text-[0.9375rem] text-ink-soft">
        {t("cases_p")} <strong className="text-ink">{groundLabel}</strong>.
      </p>

      {failed ? <p className="mb-0 mt-3 text-[0.9375rem] text-ink-soft">{t("cases_unavailable")}</p> : null}
      {loading ? <p className="mb-0 mt-3 text-[0.9375rem] text-ink-soft">{t("loading")}</p> : null}

      {total ? (
        <>
          <p className="mb-0 mt-4 text-[1.0625rem] font-semibold text-ink" data-testid="cases-headline">
            {fill(t("rc_won_line"), { won: counts.policyholder, total })}
          </p>
          {/* One whole split into at most three parts: a tall segmented bar, each block labelled with its count. */}
          <div
            role="img"
            aria-label={shown.map((w) => `${label(w)}: ${counts[w]}`).join(", ")}
            className="mt-3 flex h-9 w-full gap-[3px]"
          >
            {shown.map((w) => (
              <div
                key={w}
                data-segment={w}
                className={cn("flex min-w-10 items-center justify-center rounded-ctl text-[0.9375rem] font-bold", SEGMENT[w])}
                style={{ flexGrow: counts[w], flexBasis: 0 }}
              >
                {counts[w]}
              </div>
            ))}
          </div>
          <ul className="m-0 mt-2 flex list-none flex-wrap gap-x-5 gap-y-1 p-0 text-[0.8125rem] text-ink-soft" aria-hidden="true">
            {shown.map((w) => (
              <li key={w} className="flex items-center gap-1.5">
                <span className={cn("inline-block size-2.5 rounded-[2px]", SWATCH[w])} />
                {label(w)}
              </li>
            ))}
          </ul>

          <ul className="m-0 mt-4 list-none divide-y divide-line border-t border-line p-0">
            {cases.map((c) => {
              const url = typeof c.citation.source_url === "string" && /^https:\/\//.test(c.citation.source_url) ? c.citation.source_url : null;
              return (
                <li key={c.case_id} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-2.5">
                  <span className="min-w-0 text-[0.9375rem] text-ink">
                    {caseTitle(c)}
                    {typeof c.days_to_decision === "number" ? (
                      <span className="text-ink-soft">
                        {" "}
                        · {fill(t("cases_days_n" as Key), { n: c.days_to_decision })}
                      </span>
                    ) : null}
                  </span>
                  <span className="flex items-center gap-3">
                    <WinnerBadge prevailed={c.policyholder_prevailed} />
                    {url ? (
                      <a href={url} target="_blank" rel="noopener noreferrer" className="text-[0.875rem] font-semibold text-ink underline decoration-ink/40 decoration-1 underline-offset-4 hover:decoration-ink">
                        {t("cases_read")}
                      </a>
                    ) : null}
                  </span>
                </li>
              );
            })}
          </ul>
          <p className="mb-0 mt-3 text-[0.8125rem] text-ink-soft">
            {t("cases_note")} {t("cases_won_note")}
          </p>
          <p className="mb-0 mt-2 text-[0.9375rem]">
            <Link to={`/cases?ground=${encodeURIComponent(ground)}`} className="font-semibold text-ink underline decoration-ink/40 decoration-1 underline-offset-4 hover:decoration-ink">
              {t("cases_all_link")}
            </Link>
          </p>
        </>
      ) : null}
    </section>
  );
}
