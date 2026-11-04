import { useMemo, useState } from "react";
import { Accordion } from "@/components/ds/Accordion";
import { EmptyState } from "@/components/ds/EmptyState";
import { PageHeader } from "@/components/ds/PageHeader";
import { Container, Section } from "@/components/ds/Section";
import { inputStyles } from "@/components/ds/Field";
import { IconSearch } from "@/components/icons";
import { FAQ } from "@/content/faq";
import { HELP_GROUPS } from "@/content/help";
import { cn } from "@/lib/utils";
import { useSession } from "@/state/store";

const norm = (s: string) => s.toLowerCase();

/** Help centre: grouped accessible accordions plus a client-side search over every question and answer. */
export default function Help() {
  const { t } = useSession();
  const [query, setQuery] = useState("");
  const q = norm(query.trim());

  const groups = useMemo(() => {
    const all = [{ id: "faq", title: "Frequently asked questions", items: FAQ.map((f) => ({ id: `faq-${f.id}`, q: f.q, a: f.a })) }, ...HELP_GROUPS];
    if (!q) return all;
    return all
      .map((g) => ({ ...g, items: g.items.filter((it) => norm(it.q).includes(q) || it.a.some((p) => norm(p).includes(q))) }))
      .filter((g) => g.items.length);
  }, [q]);
  const count = groups.reduce((n, g) => n + g.items.length, 0);

  return (
    <>
      <PageHeader title="Help centre" lead="Answers about documents, terms, the assessment and what to do when an upload does not work." />
      <Section className="pt-10 md:pt-14">
        <div className="mx-auto max-w-3xl">
          <form role="search" onSubmit={(e) => e.preventDefault()} aria-label={t("help_search_label")}>
            <label htmlFor="help-search" className="mb-1 block font-semibold text-ink">
              {t("help_search_label")}
            </label>
            <div className="relative">
              <IconSearch size={20} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-soft" />
              <input
                id="help-search"
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("help_search_ph")}
                autoComplete="off"
                className={cn(inputStyles, "pl-10")}
              />
            </div>
            <p role="status" aria-live="polite" className="mb-0 mt-2 min-h-6 text-control text-ink-soft">
              {q ? `${count} ${count === 1 ? t("help_result") : t("help_results")}` : ""}
            </p>
          </form>
        </div>
      </Section>
      <Section tone="ivory" className="pt-0 md:pt-0">
        <Container className="max-w-3xl space-y-14 px-4 md:px-6">
          {count === 0 ? (
            <EmptyState title={t("help_none_title")} headingLevel={2}>
              <p className="m-0">{t("help_none_body")}</p>
            </EmptyState>
          ) : null}
          {groups.map((g) => (
            <section key={g.id} id={g.id} aria-labelledby={`${g.id}-h`} tabIndex={-1}>
              <h2 id={`${g.id}-h`} className="m-0 mb-4 font-display text-h2 font-medium text-ink">
                {g.title}
              </h2>
              <Accordion
                key={q}
                defaultOpen={q ? g.items.map((i) => i.id) : []}
                items={g.items.map((it) => ({ id: it.id, title: it.q, content: it.a.map((p) => <p key={p} className="m-0 mb-3 max-w-[62ch]">{p}</p>) }))}
              />
            </section>
          ))}
        </Container>
      </Section>
    </>
  );
}
