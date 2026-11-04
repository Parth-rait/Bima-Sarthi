import { Button } from "@/components/ds/Button";
import { PageHeader } from "@/components/ds/PageHeader";
import { Container, Section } from "@/components/ds/Section";
import { ART } from "@/content/art";
import { useSession } from "@/state/store";

const PRINCIPLES: Array<[string, string]> = [
  ["No false hope", "Being wrong in your favour is the worst kind of wrong. When facts are missing the app says Need more information, never Challengeable."],
  ["Show the source", "Every verdict, number and deadline sits next to its quote and the page it came from."],
  ["You confirm before the rules run", "Facts that are low-confidence or ambiguous get a human check first. The check does not run while one is waiting."],
  ["One flow, two roles", "Policyholders and helpers get the same truth. Only the wording (third person for helpers) and the printable summary change."],
  ["Independent and plain", "Not an insurer, not the regulator, not a lawyer. The product says so, and it never borrows government or insurer identity."],
];

export default function About() {
  const { t } = useSession();
  return (
    <>
      <PageHeader
        title="About Bima Sarthi"
        lead="An independent tool that checks a health-insurance claim decision against written rules, and shows its working."
        art={<img src={ART.folder} alt="Illustration: a folder with loose sheets and a gold seal on a soft peach and sky-blue background." width={420} height={420} className="aspect-square w-full max-w-sm rounded-ctl shadow-lift" />}
      />

      <Section labelledBy="who-h">
        <div className="reveal grid gap-10 lg:grid-cols-[1fr_1.4fr] lg:gap-16">
          <h2 id="who-h" className="m-0 font-display text-h2 font-medium text-ink">
            Who it is for
          </h2>
          <div className="space-y-5 max-w-[62ch]">
            <p className="m-0">
              <strong className="text-ink">Policyholders and their families</strong> checking their own health-insurance claim after a full rejection, a part-payment or a delayed cashless approval.
            </p>
            <p className="m-0">
              <strong className="text-ink">Helpers</strong>, such as Bima Sakhis and local insurance agents, checking a claim on someone else&apos;s behalf. The &quot;{t("helper")}&quot; switch in the top bar changes the wording to third person and adds a printable summary.
            </p>
            <p className="m-0">The job is the same for both: find out whether the insurer&apos;s decision is consistent with the rules, and if it may not be, know what to do next and by when.</p>
          </div>
        </div>
      </Section>

      <Section tone="champagne" labelledBy="isnot-h">
        <h2 id="isnot-h" className="reveal m-0 font-display text-h2 font-medium text-ink">
          What it is, and what it is not
        </h2>
        <div className="reveal mt-8 grid gap-10 md:grid-cols-2">
          <div>
            <h3 className="m-0 font-display text-h3 font-medium text-ink">It is</h3>
            <ul className="mt-3 list-disc space-y-2 pl-5">
              <li>A rules check: your confirmed facts compared with approved rule cards.</li>
              <li>A way to see the exact quote and page behind each finding.</li>
              <li>A plan, a checklist and a draft grievance letter you can send yourself.</li>
            </ul>
          </div>
          <div>
            <h3 className="m-0 font-display text-h3 font-medium text-ink">It is not</h3>
            <ul className="mt-3 list-disc space-y-2 pl-5">
              <li>Legal or medical advice. It says nothing about treatment or diagnosis.</li>
              <li>An insurer, the regulator, or affiliated with IRDAI, LIC or any insurer.</li>
              <li>A promise of any outcome. It never files a complaint or contacts anyone for you.</li>
            </ul>
          </div>
        </div>
      </Section>

      <Section labelledBy="method-h">
        <div className="reveal grid gap-10 lg:grid-cols-[1fr_1.4fr] lg:gap-16">
          <h2 id="method-h" className="m-0 max-w-[14ch] font-display text-h2 font-medium text-ink">
            Models read. Code decides.
          </h2>
          <div className="space-y-5 max-w-[62ch]">
            <p className="m-0">Models read the page images and help phrase the explanation. They never produce a verdict. Verdicts come only from a rule engine running over rule cards that a person has approved.</p>
            <p className="m-0">Each rule card quotes a regulation or policy clause, and that quote is checked word for word against its stored source page. The cards are written from published sources such as the Insurance Ombudsman Rules, 2017 and IRDAI regulations and circulars.</p>
            <p className="m-0">Written explanations pass a check that rejects any number or promise not found in the findings. Nothing here is a model we trained.</p>
          </div>
        </div>
      </Section>

      <Section tone="cream" labelledBy="princ-h">
        <h2 id="princ-h" className="reveal m-0 font-display text-h2 font-medium text-ink">
          Principles
        </h2>
        <dl className="reveal mt-8 grid gap-x-16 gap-y-8 md:grid-cols-2">
          {PRINCIPLES.map(([title, body]) => (
            <div key={title} className="border-t border-brass pt-4">
              <dt className="font-display text-[1.25rem] font-medium text-ink">{title}</dt>
              <dd className="m-0 mt-2 max-w-[48ch]">{body}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section labelledBy="limits-h">
        <div className="reveal grid gap-10 lg:grid-cols-[1fr_1.4fr] lg:gap-16">
          <h2 id="limits-h" className="m-0 font-display text-h2 font-medium text-ink">
            Limits, stated plainly
          </h2>
          <ul className="m-0 max-w-[62ch] list-disc space-y-3 pl-5">
            <li>Only health-insurance claims get a rules check. Other types get a general plan and no verdict.</li>
            <li>Rules are applied only if a card for that kind of reason exists. When none does, the app says so and notes that this does not mean the decision is correct.</li>
            <li>The Hindi text is a draft awaiting human review (Q-007). The long reading pages are English-first for now.</li>
            <li>We do not yet publish evaluation figures, so this site quotes none.</li>
            <li>Reports are not saved. A report exists only in your browser tab while your session lasts.</li>
          </ul>
        </div>
      </Section>

      <Section tone="night" labelledBy="about-cta-h">
        <Container className="reveal flex flex-wrap items-center justify-between gap-6 px-0 md:px-0">
          <h2 id="about-cta-h" className="m-0 max-w-[22ch] font-display text-h2 font-medium text-on-ink">
            Ready when you have the letter.
          </h2>
          <Button to="/check-claim" variant="onNight" size="lg">
            {t("nav_check")}
          </Button>
        </Container>
      </Section>
    </>
  );
}
