import { Link } from "react-router";
import { Button } from "@/components/ds/Button";
import { PageHeader } from "@/components/ds/PageHeader";
import { Section } from "@/components/ds/Section";
import { ART } from "@/content/art";
import { useSession } from "@/state/store";

interface Claim {
  title: string;
  body: string[];
}

/**
 * Each statement below was checked against the code on 2 Nov 2026:
 *  - folders: sarthi/app/session.py (session root, delete(), MAX_*), main.py (check deletes the folder; SESSION_TTL_S = 3600; sweeper every 300 s; DELETE /session/{sid})
 *  - not in the database / cache / logs: main.py module docstring and log calls; extract.py and explain.py call the model with cache=False
 *  - no cookies; the only thing stored in the browser is one optional display preference ("Animate the sky", key bimasarthi.sky,
 *    set in hooks/useSkyPreference.ts; a test allows browser storage in that one file only)
 */
const STORED: Claim[] = [
  {
    title: "Your files are temporary",
    body: [
      "When you press the read button, your files are written to a private temporary folder on the server, under the session root and never under the data folder.",
      "The folder is deleted as soon as the check has run, because the page images are no longer needed. If you never run the check, it is deleted after one hour at the latest. \"Delete my data now\" on the result page removes it immediately.",
    ],
  },
  {
    title: "What is kept in memory, and for how long",
    body: ["The facts read from your pages, the findings and the written explanation are held in the server's memory for your session, which lasts up to one hour. They are not written to the database. Deleting your data, or the hour passing, removes them."],
  },
  {
    title: "Documents never enter the database, the model cache or the logs",
    body: [
      "Your documents and the facts read from them are not stored in the database and are not put in the model cache: every call that handles them is made with caching turned off.",
      "Server logs record request paths (which contain a random session id) and counts. They never contain document text or fact values.",
    ],
  },
  {
    title: "Reports are not saved",
    body: ["There is no stored report. The report page exists only in your browser tab while your session lasts. Its address uses a random id that is not your session id. Reloading the page, or closing the tab, ends it."],
  },
];

const LEAVES: Claim[] = [
  {
    title: "Page images go to a model provider",
    body: [
      "To read your pages, the images are sent to a model provider. Some providers, especially on free tiers, may use the inputs they receive. We cannot control that.",
      "So while this project is being tested, please use sample or redacted documents (cover names, policy and claim numbers) rather than your originals.",
    ],
  },
  {
    title: "Nothing is sent to your insurer or the Ombudsman",
    body: ["The app does not send your documents, facts or letter to your insurer or the Ombudsman. You download the letter and send it yourself."],
  },
];

const BROWSER: Claim[] = [
  {
    title: "No account, no cookies, no trackers",
    body: ["There is no sign-in. The app itself does not set cookies, and the only thing it keeps in your browser is one optional display setting (whether the landing-page sky is animated; no personal data). This site loads no third-party scripts, fonts or analytics: even the fonts are served from the same place as the page."],
  },
  {
    title: "Previews stay in your browser",
    body: ["The thumbnails you see after choosing files are made in your browser. A file is sent to the server only when you press the read button."],
  },
  {
    title: "Public judgments only",
    body: ["The Real cases page shows public judgments, never users' documents, and is marked \"powered by IKanoon\"."],
  },
];

function Block({ heading, id, claims, tone }: { heading: string; id: string; claims: Claim[]; tone?: "champagne" | "ivory" }) {
  return (
    <Section tone={tone ?? "ivory"} labelledBy={id}>
      <div className="reveal grid gap-10 lg:grid-cols-[1fr_1.7fr] lg:gap-16">
        <h2 id={id} className="m-0 font-display text-h2 font-medium text-ink">
          {heading}
        </h2>
        <div className="space-y-8">
          {claims.map((c) => (
            <div key={c.title} className="border-t border-brass pt-4">
              <h3 className="m-0 font-display text-h3 font-medium text-ink">{c.title}</h3>
              {c.body.map((p) => (
                <p key={p} className="mb-0 mt-3 max-w-[62ch]">
                  {p}
                </p>
              ))}
            </div>
          ))}
        </div>
      </div>
    </Section>
  );
}

export default function Privacy() {
  const { t } = useSession();
  return (
    <>
      <PageHeader
        title="Privacy"
        lead="What happens to your documents, in plain words. Every statement on this page was checked against how the app actually works."
        art={<img src={ART.folder} alt="Illustration: a folder with a gold seal on a soft peach and sky-blue background." width={420} height={420} className="aspect-square w-full max-w-sm rounded-ctl shadow-lift" />}
      />
      <Block heading="What is stored, and for how long" id="stored-h" claims={STORED} />
      <Block heading="What leaves the server" id="leaves-h" claims={LEAVES} tone="champagne" />
      <Block heading="In your browser" id="browser-h" claims={BROWSER} />
      <Section tone="night" labelledBy="priv-cta-h">
        <div className="flex flex-wrap items-center justify-between gap-6">
          <div>
            <h2 id="priv-cta-h" className="m-0 font-display text-h2 font-medium text-on-night">
              Questions about your data?
            </h2>
            <p className="mb-0 mt-2 max-w-[52ch] text-on-night-soft">
              The <Link to="/help#faq" className="text-brass-light">Help centre</Link> has more answers. This page describes the app as built today; if it changes, this page changes with it.
            </p>
          </div>
          <Button to="/check-claim" variant="onNight" size="lg">
            {t("nav_check")}
          </Button>
        </div>
      </Section>
    </>
  );
}
