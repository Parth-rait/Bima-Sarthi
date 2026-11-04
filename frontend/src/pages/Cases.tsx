import { Suspense, lazy, useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, type GalleryCase, type GalleryList } from "@/api";
import { Boundary } from "@/components/ds/Boundary";
import { Button } from "@/components/ds/Button";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { Loader } from "@/components/ds/Loader";
import { PageHeader } from "@/components/ds/PageHeader";
import { Section } from "@/components/ds/Section";
import { StatusBadge, Tag } from "@/components/ds/StatusBadge";
import { VerdictCard, sortFindings } from "@/components/Verdict";
import { ART, type ArtKey } from "@/content/art";
import { SCENARIOS } from "@/content/scenarios";
import { ATTRIBUTION } from "@/i18n";
import { useMediaQuery, usePrefersReducedMotion } from "@/hooks/useMedia";
import { useSession } from "@/state/store";

const Carousel = lazy(() => import("@/components/ui/carousel"));
const DraggableScenarios = lazy(() => import("@/components/landing/DraggableScenarios"));

const isHttps = (u: unknown): u is string => typeof u === "string" && /^https:\/\//.test(u);
const ART_CYCLE: ArtKey[] = ["letter", "schedule", "timeline", "folder"];

function Scenarios() {
  const { t } = useSession();
  const wide = useMediaQuery("(min-width: 1024px)");
  const reduce = usePrefersReducedMotion();
  const [round, setRound] = useState(0);
  const list = (
    <ul className="m-0 list-none space-y-6 p-0 lg:hidden">
      {SCENARIOS.map((s) => (
        <li key={s.id} className="border border-line bg-paper p-5">
          <h3 className="m-0 font-display text-h3 font-medium text-ink">{s.title}</h3>
          <p className="mb-0 mt-2">{s.body}</p>
          <p className="mb-0 mt-3">
            <Tag tone="warm">{t("cases_illustrative")}</Tag>
          </p>
        </li>
      ))}
    </ul>
  );
  return (
    <>
      {list}
      {wide ? (
        <div className="hidden lg:block">
          <Boundary fallback={null}>
            <Suspense fallback={<Loader label={t("loading")} />}>
              <DraggableScenarios key={round} scenarios={SCENARIOS} />
            </Suspense>
          </Boundary>
          {reduce ? null : (
            <div className="mt-2">
              <Button variant="quiet" onClick={() => setRound((r) => r + 1)}>
                {t("cases_reset")}
              </Button>
            </div>
          )}
        </div>
      ) : null}
    </>
  );
}

function CaseDetail({ c, onClose }: { c: GalleryCase; onClose: () => void }) {
  const { t } = useSession();
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    ref.current?.focus();
  }, [c.case_id]);
  return (
    <section ref={ref} tabIndex={-1} aria-labelledby="case-h" className="border border-line bg-paper p-5 shadow-sheet md:p-8">
      <h3 id="case-h" className="m-0 font-display text-h3 font-medium text-ink">
        {c.citation.case_number || c.case_id}
      </h3>
      <p className="mb-0 mt-1 text-ink-soft">{[c.citation.forum, c.citation.decided_on, c.insurer].filter(Boolean).join(", ")}</p>
      <p className="mb-0 mt-3">
        <strong>{t("outcome")}: </strong>
        {c.outcome || ""}
      </p>
      <div className="wf mt-4">
        <div className="findings">
          {sortFindings(c.findings).map((f, i) => (
            <VerdictCard key={`${f.rule_id}-${i}`} f={f} i={i} />
          ))}
        </div>
      </div>
      <p className="mb-0 mt-4 text-control text-ink-soft">
        {isHttps(c.citation.source_url) ? (
          <a href={c.citation.source_url} rel="noopener noreferrer" className="text-ink">
            {t("srcurl")}
          </a>
        ) : null}{" "}
        {c.attribution || t("powered")}
      </p>
      <div className="mt-4">
        <Button variant="secondary" onClick={onClose}>
          {t("cases_close")}
        </Button>
      </div>
    </section>
  );
}

/**
 * Real, cited judgments from GET /gallery, plus clearly labelled illustrative scenarios. Never a real person's history:
 * a verified case is shown only as the public citation and the rule findings the engine produced for it.
 */
export default function Cases() {
  const { t } = useSession();
  const [list, setList] = useState<GalleryList | null>(null);
  const [open, setOpen] = useState<GalleryCase | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const detailAnchor = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      setList(await api.gallery());
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err"));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => void load(), [load]);

  const openCase = useCallback(
    async (id: string) => {
      setErr(null);
      try {
        setOpen(await api.galleryCase(id));
        detailAnchor.current?.scrollIntoView?.({ block: "start" });
      } catch (e) {
        setErr(e instanceof ApiError ? e.message : t("err"));
      }
    },
    [t],
  );

  const cases = list?.cases ?? [];
  const label = (c: GalleryList["cases"][number]) => c.citation.case_number || c.case_id;
  const slides = [
    ...cases.map((c, i) => ({
      title: `${t("cases_verified")}: ${label(c)}`,
      button: t("open_case"),
      src: ART[ART_CYCLE[i % ART_CYCLE.length]],
      alt: "Decorative artwork: a document on a soft peach and sky-blue background. It does not show the case itself.",
      onSelect: () => void openCase(c.case_id),
    })),
    ...SCENARIOS.map((s) => ({ title: `${t("cases_illustrative")}: ${s.title}`, button: "", src: ART[s.art], alt: s.artAlt })),
  ];

  return (
    <>
      <PageHeader title={t("cases_h")} lead={t("g_p")} />

      <Section tone="night" labelledBy="car-h">
        <h2 id="car-h" className="m-0 font-display text-h2 font-medium text-on-ink">
          {t("cases_browse")}
        </h2>
        <p className="mt-3 max-w-[60ch] text-on-ink-soft">{t("cases_browse_p")}</p>
        <div className="relative overflow-hidden pb-24 pt-10">
          <Boundary fallback={<p className="text-on-ink-soft">{t("cases_carousel_fail")}</p>}>
            <Suspense fallback={<Loader label={t("loading")} />}>
              <Carousel slides={slides} label={t("cases_h")} />
            </Suspense>
          </Boundary>
        </div>
      </Section>

      <Section labelledBy="ver-h">
        <h2 id="ver-h" className="m-0 font-display text-h2 font-medium text-ink">
          {t("cases_verified_h")}
        </h2>
        <p role="status" className="mb-0 mt-2 min-h-6 text-ink-soft">
          {loading ? t("gallery_loading") : ""}
        </p>
        {err ? (
          <ErrorState title={t("err")} what={err} next={t("cases_retry_next")} className="mt-4">
            <Button variant="secondary" onClick={() => void load()}>
              {t("svc_retry")}
            </Button>
          </ErrorState>
        ) : null}
        {list && !cases.length && !loading ? (
          <EmptyState title={t("g_empty")} className="mt-6">
            <p className="m-0">{t("cases_empty_p")}</p>
          </EmptyState>
        ) : null}
        {cases.length ? (
          <ul className="m-0 mt-6 list-none divide-y divide-line border-y border-line p-0">
            {cases.map((c) => (
              <li key={c.case_id} className="flex flex-wrap items-center justify-between gap-4 py-5">
                <div>
                  <h3 className="m-0 font-display text-h3 font-medium text-ink">{label(c)}</h3>
                  <p className="mb-0 mt-1 text-ink-soft">{[c.citation.forum, c.citation.decided_on].filter(Boolean).join(", ")}</p>
                  <p className="mb-0 mt-2 flex flex-wrap gap-2">
                    {c.verdicts.map((v, i) => (
                      <StatusBadge key={`${v}-${i}`} verdict={v} />
                    ))}
                  </p>
                </div>
                <Button variant="secondary" onClick={() => void openCase(c.case_id)}>
                  {t("open_case")}
                  <span className="sr-only"> {label(c)}</span>
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
        <div ref={detailAnchor} className="mt-8">
          {open ? <CaseDetail c={open} onClose={() => setOpen(null)} /> : null}
        </div>
        <p className="mb-0 mt-6 text-control text-ink-soft">{list?.attribution || ATTRIBUTION}</p>
      </Section>

      <Section tone="champagne" labelledBy="ill-h">
        <div>
          <h2 id="ill-h" className="m-0 font-display text-h2 font-medium text-ink">
            {t("cases_illustrative_h")}
          </h2>
          <p className="mb-8 mt-3 max-w-[62ch]">{t("cases_illustrative_p")}</p>
          <Scenarios />
        </div>
      </Section>
    </>
  );
}
