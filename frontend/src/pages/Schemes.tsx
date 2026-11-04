import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api } from "@/api";
import type { Bilingual, SchemeAnswers, SchemeCatalogue, SchemeGroupKey, SchemeMatch, SchemeQuestionId, SchemeResult, SchemeStatus } from "@/api";
import { Accordion } from "@/components/ds/Accordion";
import { Button } from "@/components/ds/Button";
import { Band, Grid12, Wrap } from "@/components/ds/Section";
import { IconChevronDown } from "@/components/icons";
import { TaglineReveal } from "@/components/landing/TaglineReveal";
import { pick, type Lang } from "@/i18n";
import { cn } from "@/lib/utils";
import { useSession } from "@/state/store";

/*
 * Design notes: this page follows .qoder/skills/landing-page-design (one offer, one audience, one action;
 * a single typeface pair; a flat palette; named states; a tagline reveal). Three deliberate deviations for this
 * product: the existing warm palette and Source Sans 3/Fraunces stay (Devanagari support and the documented brand),
 * the hero heading is solid ink rather than a gradient (contrast for low-vision readers), and the existing line
 * icons are used instead of adding a new icon package.
 */

type Copy = {
  eyebrow: string;
  h1: string;
  lead: string;
  proof: (n: number, date: string) => string;
  start: string;
  form_h: string;
  form_p: string;
  answered: string;
  submit: string;
  submitting: string;
  required: string;
  loading_q: string;
  load_error: string;
  retry: string;
  match_error: string;
  no_store: string;
  results_h: string;
  results_p: string;
  summary: (n: number, start: number, ask: number, notNow: number) => string;
  empty_h: string;
  empty_p: string;
  checked: string;
  not_h: string;
  why: string;
  pays: string;
  who: string;
  premium: string;
  deadline: string;
  details: string;
  steps: string;
  fails: string;
  official: string;
  claim_q: string;
  claim_btn: string;
  new_tab: string;
  source: string;
  tagline: string;
  how_h: string;
  how_p: string;
  how: Array<{ title: string; body: string }>;
  includes_h: string;
  includes: string[];
  faq_h: string;
  faq_p: string;
  faq: Array<{ q: string; a: string }>;
  final_h: string;
  final_p: string;
};

const COPY: Record<Lang, Copy> = {
  en: {
    eyebrow: "Maharashtra · Agriculture workers",
    h1: "Find the schemes that fit your work.",
    lead: "Answer four short questions about your work, age and bank account. See which agriculture schemes fit, what each one pays, and how a claim can fail.",
    proof: (n, date) => `${n} schemes. Each one linked to its official source. Checked on ${date}.`,
    start: "Answer four questions",
    form_h: "Four questions",
    form_p: "There is no right answer. Pick the one that is closest. You can change any answer.",
    answered: "answered",
    submit: "Show my schemes",
    submitting: "Checking your answers",
    required: "Answer all four questions first. The first unanswered one is marked.",
    loading_q: "Loading the questions",
    load_error: "The questions could not load. Check your connection and try again.",
    retry: "Try again",
    match_error: "We could not check your answers. Check your connection and try again.",
    no_store: "Your answers are used for this check only. Nothing is saved.",
    results_h: "Your schemes",
    results_p: "Grouped by what to do next. The reason under each scheme uses your four answers.",
    summary: (n, start, ask, notNow) => `${n} schemes: ${start} to start, ${ask} to ask about, ${notNow} that ${notNow === 1 ? "does" : "do"} not fit.`,
    empty_h: "Your answers will appear here",
    empty_p: "Answer the four questions above. The schemes are grouped by what to do next.",
    checked: "Checked on",
    not_h: "What this finder is not",
    why: "Why this result",
    pays: "What it pays",
    who: "Who can get it",
    premium: "Premium",
    deadline: "Deadline",
    details: "Read the steps and how a claim can fail",
    steps: "What to do",
    fails: "How a claim can fail",
    official: "Open the official page",
    claim_q: "Was a claim under this scheme turned down or paid short?",
    claim_btn: "Check the rejection letter",
    new_tab: "opens in a new tab",
    source: "Official source",
    tagline: "Four questions, seven schemes.",
    how_h: "How the finder decides",
    how_p: "It is a rules check, not a guess. Your answers are compared with the conditions written on each scheme's official page.",
    how: [
      { title: "Answer four questions", body: "Work, age, bank account and ration card. Pick the closest answer." },
      { title: "Read three groups", body: "Start with, ask about and not now. Every scheme says which condition matched or needs checking." },
      { title: "Take the paper to the office", body: "Each scheme lists the documents and the ways a claim can fail. The office or insurer makes the final decision." },
    ],
    includes_h: "What every result includes",
    includes: ["A status in plain words, with one reason.", "The amount it pays and who can get it.", "The steps, the documents and how a claim can fail."],
    faq_h: "Questions people ask",
    faq_p: "Short answers about eligibility, documents and what happens to your answers.",
    faq: [
      { q: "Does this mean I am approved?", a: "No. The finder compares your answers with written conditions. The office or insurer decides." },
      { q: "What is the 7/12 extract?", a: "It is the State land record that names the person who farms a plot. Some schemes ask for it." },
      { q: "Why does a scheme say to check with the office?", a: "One condition could not be settled from four answers, such as an exact age or a bank account. The office can confirm it." },
      { q: "I have no bank account. Can I still get help?", a: "Some schemes need an individual bank or post office account. Ask about opening a basic account, and read the schemes in the ask group." },
      { q: "Are my answers saved?", a: "No. The finder does not create an account or store your answers. They are used only to show this result." },
      { q: "Is this only for Maharashtra?", a: "Yes. This first list covers agriculture workers in Maharashtra." },
      { q: "How current is this information?", a: "Each scheme shows its official source and the date it was read. Rules and amounts can change, so confirm at the office." },
    ],
    final_h: "Find the schemes that fit your work.",
    final_p: "Four questions, seven sourced schemes, and a plain reason for every answer.",
  },
  hi: {
    eyebrow: "महाराष्ट्र · कृषि श्रमिक",
    h1: "अपने काम के अनुसार योजनाएँ खोजें।",
    lead: "अपने काम, उम्र और बैंक खाते के बारे में चार छोटे सवालों के जवाब दें। देखें कौन सी कृषि योजनाएँ मिलती हैं, हर योजना कितना देती है, और दावा कैसे ख़त्म हो सकता है।",
    proof: (n, date) => `${n} योजनाएँ। हर योजना का आधिकारिक स्रोत। ${date} को जाँचा गया।`,
    start: "चार सवालों के जवाब दें",
    form_h: "चार सवाल",
    form_p: "कोई सही या ग़लत जवाब नहीं है। जो सबसे मिलता हो वह चुनें। आप कोई भी जवाब बदल सकते हैं।",
    answered: "उत्तर दिए",
    submit: "मेरी योजनाएँ दिखाएँ",
    submitting: "आपके जवाब देखे जा रहे हैं",
    required: "पहले चारों सवालों के जवाब दें। पहला बिना उत्तर वाला सवाल चिह्नित है।",
    loading_q: "सवाल लोड हो रहे हैं",
    load_error: "सवाल लोड नहीं हो सके। अपना कनेक्शन देखें और फिर कोशिश करें।",
    retry: "फिर कोशिश करें",
    match_error: "हम आपके जवाब नहीं जाँच सके। अपना कनेक्शन देखें और फिर कोशिश करें।",
    no_store: "आपके जवाब सिर्फ़ इसी जाँच के लिए हैं। कुछ भी सहेजा नहीं जाता।",
    results_h: "आपकी योजनाएँ",
    results_p: "आगे क्या करना है, उसके अनुसार समूह। हर योजना के नीचे का कारण आपके चार जवाबों से है।",
    summary: (n, start, ask, notNow) => `${n} योजनाएँ: ${start} से शुरू करें, ${ask} के बारे में पूछें, ${notNow} अभी नहीं।`,
    empty_h: "आपके जवाब यहाँ दिखेंगे",
    empty_p: "ऊपर चारों सवालों के जवाब दें। योजनाएँ इसके अनुसार समूहों में दिखेंगी कि आगे क्या करना है।",
    checked: "जाँचा गया",
    not_h: "यह खोज क्या नहीं है",
    why: "यह नतीजा क्यों",
    pays: "कितना मिलता है",
    who: "कौन पा सकता है",
    premium: "प्रीमियम",
    deadline: "अंतिम तारीख़",
    details: "कदम और दावा कैसे ख़त्म हो सकता है, पढ़ें",
    steps: "क्या करें",
    fails: "दावा कैसे ख़त्म हो सकता है",
    official: "आधिकारिक पृष्ठ खोलें",
    claim_q: "क्या इस योजना का दावा ठुकराया गया या कम भुगतान हुआ?",
    claim_btn: "अस्वीकृति पत्र जाँचें",
    new_tab: "नई विंडो में खुलता है",
    source: "आधिकारिक स्रोत",
    tagline: "चार सवाल, सात योजनाएँ।",
    how_h: "खोज कैसे तय करती है",
    how_p: "यह नियमों की जाँच है, अंदाज़ा नहीं। आपके जवाब हर योजना के आधिकारिक पृष्ठ पर लिखी शर्तों से मिलाए जाते हैं।",
    how: [
      { title: "चार सवालों के जवाब दें", body: "काम, उम्र, बैंक खाता और राशन कार्ड। जो सबसे मिलता हो वह चुनें।" },
      { title: "तीन समूह पढ़ें", body: "इनसे शुरू करें, इनके बारे में पूछें, और अभी नहीं। हर योजना बताती है कौन सी शर्त मिली या जाँचनी है।" },
      { title: "कागज़ लेकर कार्यालय जाएँ", body: "हर योजना में कागज़ और दावा ख़त्म होने के कारण दिए हैं। अंतिम फ़ैसला कार्यालय या बीमाकर्ता करता है।" },
    ],
    includes_h: "हर नतीजे में क्या मिलता है",
    includes: ["आसान शब्दों में स्थिति, और एक कारण।", "कितनी राशि मिलती है और कौन पा सकता है।", "कदम, कागज़, और दावा कैसे ख़त्म हो सकता है।"],
    faq_h: "लोग क्या पूछते हैं",
    faq_p: "पात्रता, कागज़ों और आपके जवाबों के बारे में छोटे जवाब।",
    faq: [
      { q: "क्या इसका मतलब है कि मंज़ूरी मिल गई?", a: "नहीं। खोज आपके जवाब लिखित शर्तों से मिलाती है। फ़ैसला कार्यालय या बीमाकर्ता करता है।" },
      { q: "७/१२ उतारा क्या है?", a: "यह राज्य का भूमि रिकॉर्ड है जिसमें उस व्यक्ति का नाम होता है जो ज़मीन पर खेती करता है। कुछ योजनाएँ इसे माँगती हैं।" },
      { q: "किसी योजना में कार्यालय से पूछने को क्यों कहा गया है?", a: "चार जवाबों से एक शर्त तय नहीं होती, जैसे सही उम्र या बैंक खाता। कार्यालय उसे पक्का कर सकता है।" },
      { q: "मेरा बैंक खाता नहीं है। क्या मदद मिल सकती है?", a: "कुछ योजनाओं के लिए अपना बैंक या डाकघर खाता चाहिए। साधारण खाता खोलने के बारे में पूछें, और 'इनके बारे में पूछें' समूह की योजनाएँ पढ़ें।" },
      { q: "क्या मेरे जवाब सहेजे जाते हैं?", a: "नहीं। खोज कोई खाता नहीं बनाती और आपके जवाब नहीं रखती। वे सिर्फ़ यह नतीजा दिखाने के लिए हैं।" },
      { q: "क्या यह सिर्फ़ महाराष्ट्र के लिए है?", a: "हाँ। यह पहली सूची महाराष्ट्र के कृषि श्रमिकों के लिए है।" },
      { q: "यह जानकारी कितनी नई है?", a: "हर योजना अपना आधिकारिक स्रोत और पढ़ने की तारीख़ दिखाती है। नियम और राशि बदल सकते हैं, इसलिए कार्यालय में पक्का करें।" },
    ],
    final_h: "अपने काम के अनुसार योजनाएँ खोजें।",
    final_p: "चार सवाल, स्रोत वाली सात योजनाएँ, और हर जवाब के साथ सीधा कारण।",
  },
};

const GROUP_ORDER: SchemeGroupKey[] = ["start", "ask", "not_now"];

function formatDate(iso: string, lang: Lang): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(lang === "hi" ? "hi-IN" : "en-IN", { day: "numeric", month: "long", year: "numeric" }).format(d);
}

function SchemeGlyph({ status }: { status: SchemeStatus }) {
  if (status === "likely") {
    return (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
        <circle cx="12" cy="12" r="8.5" />
        <path d="m8.4 12.3 2.5 2.5 4.7-5" />
      </svg>
    );
  }
  if (status === "check") {
    return (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
        <path d="M12 3.5 20.5 12 12 20.5 3.5 12 12 3.5Z" />
        <path d="M9.8 9.7a2.3 2.3 0 1 1 3.3 2c-.7.4-1.1.9-1.1 1.6" />
        <path d="M12 16.4v.01" />
      </svg>
    );
  }
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <rect x="4" y="4" width="16" height="16" rx="1.5" />
      <path d="m9 9 6 6M15 9l-6 6" />
    </svg>
  );
}

function StatusTag({ status, label }: { status: SchemeStatus; label: string }) {
  const tone =
    status === "likely"
      ? "border-sage-ink/40 bg-sage-wash text-sage-ink"
      : status === "check"
        ? "border-amber-ink/40 bg-amber-wash text-amber-ink"
        : "border-terracotta-ink/40 bg-terracotta-wash text-terracotta-ink";
  return (
    <span data-status={status} className={cn("inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-semibold", tone)}>
      <SchemeGlyph status={status} />
      <span>{label}</span>
    </span>
  );
}

function SchemeCard({ result, lang, c }: { result: SchemeResult; lang: Lang; c: Copy }) {
  const label = (b: Bilingual) => pick(b, lang);
  return (
    <article className="flex flex-col rounded-card bg-paper p-4 sm:p-6">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <StatusTag status={result.status} label={label(result.status_label)} />
        <p className="m-0 text-sm text-ink-soft">{label(result.status_sentence)}</p>
      </div>
      <h3 className="m-0 mt-4 font-display text-xl font-semibold text-ink sm:text-2xl">{label(result.name)}</h3>
      <p className="m-0 mt-2 text-base text-ink-soft">{label(result.short)}</p>

      <div className="mt-4 rounded-ctl bg-peach p-4">
        <p className="m-0 text-sm font-semibold text-ink">{c.why}</p>
        <p className="m-0 mt-1 text-base text-ink">{label(result.why)}</p>
      </div>

      <dl className="m-0 mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <dt className="text-sm font-semibold text-ink-soft">{c.pays}</dt>
          <dd className="m-0 mt-1 text-base text-ink">{label(result.cover)}</dd>
        </div>
        <div>
          <dt className="text-sm font-semibold text-ink-soft">{c.who}</dt>
          <dd className="m-0 mt-1 text-base text-ink">{label(result.eligibility)}</dd>
        </div>
      </dl>

      {result.premium || result.deadline ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {result.premium ? (
            <div className="rounded-ctl bg-ivory p-3">
              <p className="m-0 text-sm font-semibold text-ink-soft">{c.premium}</p>
              <p className="m-0 mt-1 text-base text-ink">{label(result.premium)}</p>
            </div>
          ) : null}
          {result.deadline ? (
            <div className="rounded-ctl bg-ivory p-3">
              <p className="m-0 text-sm font-semibold text-ink-soft">{c.deadline}</p>
              <p className="m-0 mt-1 text-base text-ink">{label(result.deadline)}</p>
            </div>
          ) : null}
        </div>
      ) : null}

      {result.claim_product_line ? (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-ctl bg-ivory p-3">
          <p className="m-0 text-base text-ink">{c.claim_q}</p>
          <Button to={`/check-claim?type=${result.claim_product_line}`} variant="secondary" size="sm">
            {c.claim_btn}
          </Button>
        </div>
      ) : null}

      <details className="group mt-4 pt-4">
        <summary className="flex min-h-11 cursor-pointer list-none [&::-webkit-details-marker]:hidden items-center justify-between gap-3 rounded-ctl px-2 py-2 font-semibold text-ink hover:bg-peach">
          <span>{c.details}</span>
          <IconChevronDown size={22} className="shrink-0 transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] group-open:rotate-180 motion-reduce:transition-none" />
        </summary>
        <div className="mt-4 grid gap-6 sm:grid-cols-2">
          <div>
            <h4 className="m-0 text-base font-semibold text-ink">{c.steps}</h4>
            <ol className="m-0 mt-2 list-decimal space-y-2 pl-5 text-base text-ink">
              {result.steps.map((s, i) => (
                <li key={i}>{label(s)}</li>
              ))}
            </ol>
          </div>
          <div>
            <h4 className="m-0 text-base font-semibold text-ink">{c.fails}</h4>
            <ul className="m-0 mt-2 list-disc space-y-2 pl-5 text-base text-ink">
              {result.fails.map((f, i) => (
                <li key={i}>{label(f)}</li>
              ))}
            </ul>
          </div>
        </div>
        <div className="mt-5 pt-4 text-sm text-ink">
          <p className="m-0">
            <a href={result.official_url} target="_blank" rel="noreferrer">
              {c.official}
              <span className="sr-only"> ({c.new_tab})</span>
            </a>
          </p>
          <p className="m-0 mt-2">
            {c.source}:{" "}
            <a href={result.source.url} target="_blank" rel="noreferrer">
              {label(result.source.name)}
              <span className="sr-only"> ({c.new_tab})</span>
            </a>
            . {label(result.source.note)}
          </p>
          <p className="m-0 mt-1 text-ink-soft">
            {c.checked} {formatDate(result.verified_on, lang)}.
          </p>
        </div>
      </details>
    </article>
  );
}

export default function Schemes() {
  const { state } = useSession();
  const lang = state.lang;
  const c = COPY[lang];

  const [catalogue, setCatalogue] = useState<SchemeCatalogue | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [reload, setReload] = useState(0);

  const [answers, setAnswers] = useState<Partial<Record<SchemeQuestionId, string>>>({});
  const [match, setMatch] = useState<SchemeMatch | null>(null);
  const [matching, setMatching] = useState(false);
  const [matchError, setMatchError] = useState(false);
  const [formError, setFormError] = useState(false);

  const formRef = useRef<HTMLFormElement>(null);
  const resultsRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setLoadError(false);
    api
      .schemes()
      .then((data) => {
        if (alive) setCatalogue(data);
      })
      .catch(() => {
        if (alive) setLoadError(true);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [reload]);

  useEffect(() => {
    if (match) resultsRef.current?.focus();
  }, [match]);

  const questions = catalogue?.questions ?? [];
  const answered = questions.filter((q) => answers[q.id]).length;

  const choose = (id: SchemeQuestionId, value: string) => {
    setAnswers((cur) => ({ ...cur, [id]: value }));
    setFormError(false);
    setMatchError(false);
    if (match) setMatch(null);
  };

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const missing = questions.find((q) => !answers[q.id]);
    if (missing) {
      setFormError(true);
      formRef.current?.querySelector<HTMLInputElement>(`input[name="${missing.id}"]`)?.focus();
      return;
    }
    const body = Object.fromEntries(questions.map((q) => [q.id, answers[q.id]])) as unknown as SchemeAnswers;
    setFormError(false);
    setMatchError(false);
    setMatching(true);
    try {
      setMatch(await api.matchSchemes(body));
    } catch {
      setMatchError(true);
    } finally {
      setMatching(false);
    }
  }

  let finder: ReactNode;
  if (loading) {
    finder = (
      <div aria-busy="true" className="rounded-card bg-paper p-4 sm:p-6">
        <p role="status" className="m-0 text-sm font-semibold text-ink-soft">
          {c.loading_q}
        </p>
        <div className="mt-6 animate-pulse space-y-6 motion-reduce:animate-none">
          {[0, 1, 2, 3].map((i) => (
            <div key={i}>
              <div className="h-5 w-40 rounded bg-peach" />
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <div className="h-12 rounded-ctl bg-ivory" />
                <div className="h-12 rounded-ctl bg-ivory" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  } else if (loadError || !catalogue) {
    finder = (
      <div role="alert" className="rounded-card border border-terracotta bg-terracotta-wash p-4 text-terracotta-ink sm:p-6">
        <p className="m-0 font-semibold">{c.load_error}</p>
        <Button variant="secondary" className="mt-4" onClick={() => setReload((n) => n + 1)}>
          {c.retry}
        </Button>
      </div>
    );
  } else {
    finder = (
      <form ref={formRef} onSubmit={onSubmit} noValidate aria-describedby={formError ? "scheme-form-error" : undefined} className="rounded-card bg-paper p-4 sm:p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 className="m-0 font-display text-2xl font-semibold text-ink">{c.form_h}</h2>
          <p className="m-0 text-sm text-ink-soft">
            {answered} / {questions.length} {c.answered}
          </p>
        </div>
        <p className="m-0 mt-2 text-base text-ink-soft">{c.form_p}</p>

        <div className="mt-6 space-y-6">
          {questions.map((q) => (
            <fieldset key={q.id} className="m-0 min-w-0 border-0 p-0">
              <legend className="p-0 font-semibold text-ink">{pick(q.text, lang)}</legend>
              <p className="m-0 mt-1 text-sm text-ink-soft">{pick(q.hint, lang)}</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {q.options.map((o) => {
                  const selected = answers[q.id] === o.value;
                  return (
                    <label
                      key={o.value}
                      className={cn(
                        "flex min-h-12 cursor-pointer items-center gap-3 rounded-ctl border px-4 py-3 text-base text-ink",
                        selected ? "border-ink bg-peach" : "border-line-strong bg-ivory hover:bg-peach",
                      )}
                    >
                      <input type="radio" name={q.id} value={o.value} checked={selected} onChange={() => choose(q.id, o.value)} required className="size-5 shrink-0 accent-ink" />
                      <span>{pick(o.label, lang)}</span>
                    </label>
                  );
                })}
              </div>
            </fieldset>
          ))}
        </div>

        {formError ? (
          <p id="scheme-form-error" role="alert" className="m-0 mt-4 rounded-ctl bg-amber-wash px-3 py-2 text-sm font-semibold text-amber-ink">
            {c.required}
          </p>
        ) : null}
        {matchError ? (
          <p role="alert" className="m-0 mt-4 rounded-ctl bg-terracotta-wash px-3 py-2 text-sm font-semibold text-terracotta-ink">
            {c.match_error}
          </p>
        ) : null}

        <div className="mt-6 flex flex-wrap items-center gap-4">
          <Button type="submit" variant="primary" size="lg" loading={matching} loadingLabel={c.submitting}>
            {c.submit}
          </Button>
          <p className="m-0 max-w-[34ch] text-sm text-ink-soft">{c.no_store}</p>
        </div>
      </form>
    );
  }

  const counts = { start: 0, ask: 0, not_now: 0 };
  for (const r of match?.results ?? []) counts[r.group] += 1;

  return (
    <>
      <Band tone="peach" labelledBy="schemes-h" pad="tight">
        <Wrap width="wide">
          <Grid12 className="items-start">
            <div className="lg:col-span-5">
              <h1 id="schemes-h" tabIndex={-1} data-page-heading className="m-0 max-w-[16ch] font-display text-display font-bold text-ink">
                {c.h1}
              </h1>
              <p className="m-0 mt-6 max-w-[680px] text-lead text-ink">{c.eyebrow}. {c.lead}</p>
              {catalogue ? <p className="m-0 mt-6 max-w-[680px] text-sm text-ink-soft">{c.proof(catalogue.scheme_count, formatDate(catalogue.checked_on, lang))}</p> : null}
              <div className="mt-8">
                <Button href="#finder" variant="primary" size="lg">
                  {c.start}
                </Button>
              </div>
            </div>
            <div id="finder" className="mt-12 scroll-mt-28 lg:col-span-6 lg:col-start-7 lg:mt-0">
              {finder}
            </div>
          </Grid12>
        </Wrap>
      </Band>

      <Band tone="ivory" labelledBy="results-heading">
        <Wrap width="wide">
          <Grid12>
            <div className="lg:col-span-3">
              <h2 id="results-heading" ref={resultsRef} tabIndex={-1} className="m-0 font-display text-3xl font-semibold text-ink sm:text-4xl">
                {c.results_h}
              </h2>
              <p className="m-0 mt-3 text-base text-ink-soft">{c.results_p}</p>
              {match ? <p className="m-0 mt-3 text-sm text-ink-soft">{c.checked} {formatDate(match.checked_on, lang)}.</p> : null}
              <div className="mt-6 rounded-card bg-peach p-4">
                <h3 className="m-0 text-base font-semibold text-ink">{c.not_h}</h3>
                <p className="m-0 mt-2 text-base text-ink">{pick(match?.disclaimer ?? catalogue?.disclaimer, lang)}</p>
              </div>
            </div>

            <div className="mt-10 lg:col-span-8 lg:col-start-5 lg:mt-0">
              {!match ? (
                <div className="rounded-card bg-paper p-4 sm:p-6">
                  <h3 className="m-0 font-display text-xl font-semibold text-ink sm:text-2xl">{c.empty_h}</h3>
                  <p className="m-0 mt-2 text-base text-ink-soft">{c.empty_p}</p>
                  {catalogue ? (
                    <ul className="m-0 mt-6 grid list-none gap-4 p-0 sm:grid-cols-3">
                      {GROUP_ORDER.map((g) => (
                        <li key={g} className="rounded-ctl bg-ivory p-4">
                          <p className="m-0 font-semibold text-ink">{pick(catalogue.groups[g].title, lang)}</p>
                          <p className="m-0 mt-2 text-sm text-ink-soft">{pick(catalogue.groups[g].intro, lang)}</p>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : (
                <div className="space-y-10">
                  <p role="status" className="m-0 text-base font-semibold text-ink">
                    {c.summary(match.results.length, counts.start, counts.ask, counts.not_now)}
                  </p>
                  {GROUP_ORDER.map((g) => {
                    const items = match.results.filter((r) => r.group === g);
                    if (items.length === 0) return null;
                    return (
                      <section key={g} aria-labelledby={`group-${g}`}>
                        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                          <div>
                            <h3 id={`group-${g}`} className="m-0 font-display text-2xl font-semibold text-ink">
                              {pick(match.groups[g].title, lang)}
                            </h3>
                            <p className="m-0 mt-2 text-base text-ink-soft">{pick(match.groups[g].intro, lang)}</p>
                          </div>
                          <p className="m-0 text-sm font-semibold text-ink-soft">
                            {items.length} {lang === "hi" ? "योजनाएँ" : items.length === 1 ? "scheme" : "schemes"}
                          </p>
                        </div>
                        <div className="mt-4 grid gap-4 xl:grid-cols-2">
                          {items.map((r) => (
                            <SchemeCard key={r.id} result={r} lang={lang} c={c} />
                          ))}
                        </div>
                      </section>
                    );
                  })}
                </div>
              )}
            </div>
          </Grid12>
        </Wrap>
      </Band>

      <Band tone="peach" labelledBy="tagline-h" pad="tight">
        <Wrap width="wide">
          <TaglineReveal id="tagline-h" text={c.tagline} />
        </Wrap>
      </Band>

      <Band tone="ivory" labelledBy="how-h">
        <Wrap width="wide">
          <Grid12>
            <div className="lg:col-span-4">
              <h2 id="how-h" className="m-0 font-display text-3xl font-semibold text-ink sm:text-4xl">
                {c.how_h}
              </h2>
              <p className="m-0 mt-4 max-w-[44ch] text-base text-ink-soft">{c.how_p}</p>
            </div>
            <ol className="m-0 grid list-none gap-6 p-0 sm:grid-cols-3 lg:col-span-7 lg:col-start-6">
              {c.how.map((s) => (
                <li key={s.title} className="rounded-card bg-paper p-4">
                  <h3 className="m-0 font-display text-xl font-semibold text-ink">{s.title}</h3>
                  <p className="m-0 mt-2 text-base text-ink">{s.body}</p>
                </li>
              ))}
            </ol>
          </Grid12>

          <div className="mt-12 pt-8">
            <h2 className="m-0 font-display text-2xl font-semibold text-ink">{c.includes_h}</h2>
            <ul className="m-0 mt-4 grid list-none gap-4 p-0 sm:grid-cols-3">
              {c.includes.map((item) => (
                <li key={item} className="flex items-start gap-3 rounded-ctl bg-peach p-4 text-base text-ink">
                  <span aria-hidden="true" className="mt-1 inline-block size-2 shrink-0 rotate-45 border border-ink" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </Wrap>
      </Band>

      <Band tone="peach" labelledBy="faq-h">
        <Wrap width="wide">
          <Grid12>
            <div className="lg:col-span-4">
              <h2 id="faq-h" className="m-0 font-display text-3xl font-semibold text-ink sm:text-4xl">
                {c.faq_h}
              </h2>
              <p className="m-0 mt-4 max-w-[40ch] text-base text-ink-soft">{c.faq_p}</p>
            </div>
            <div className="mt-8 lg:col-span-7 lg:col-start-6 lg:mt-0">
              <Accordion items={c.faq.map((f, i) => ({ id: `faq-${i}`, title: f.q, content: <p className="m-0 mb-3 max-w-[62ch] text-base text-ink">{f.a}</p> }))} />
            </div>
          </Grid12>
        </Wrap>
      </Band>

      <Band tone="ink" pad="tight">
        <Wrap width="wide">
          <div className="flex flex-wrap items-center justify-between gap-8">
            <div>
              <h2 id="final-h" className="m-0 max-w-[680px] font-display text-3xl font-semibold text-on-ink sm:text-4xl">
                {c.final_h}
              </h2>
              <p className="m-0 mt-4 max-w-[680px] text-base text-on-ink-soft">{c.final_p}</p>
            </div>
            <Button href="#finder" variant="onInk" size="lg">
              {c.start}
            </Button>
          </div>
        </Wrap>
      </Band>
    </>
  );
}
