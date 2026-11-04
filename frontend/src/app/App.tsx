import { Suspense, lazy, useRef } from "react";
import { Route, Routes } from "react-router";
import { CompanionSlot } from "@/companion/CompanionSlot";
import { Loader } from "@/components/ds/Loader";
import { ToastProvider } from "@/components/ds/Toast";
import { Footer } from "@/components/layout/Footer";
import { Navbar } from "@/components/layout/Navbar";
import { useSession } from "@/state/store";
import { RouteEffects } from "./RouteEffects";
import { Splash } from "./Splash";

// One chunk per route. The landing page is the only one most visitors need before anything else.
const Landing = lazy(() => import("@/pages/Landing"));
const Schemes = lazy(() => import("@/pages/Schemes"));
const About = lazy(() => import("@/pages/About"));
const HowItWorks = lazy(() => import("@/pages/HowItWorks"));
const CheckClaim = lazy(() => import("@/pages/CheckClaim"));
const ActionPlan = lazy(() => import("@/pages/ActionPlan"));
const Cases = lazy(() => import("@/pages/Cases"));
const Evidence = lazy(() => import("@/pages/Evidence"));
const Privacy = lazy(() => import("@/pages/Privacy"));
const Help = lazy(() => import("@/pages/Help"));
const Results = lazy(() => import("@/pages/Results"));
const NotFound = lazy(() => import("@/pages/NotFound"));
const DevComponents = lazy(() => import("@/pages/DevComponents"));

export function App() {
  const { t } = useSession();
  const mainRef = useRef<HTMLElement>(null);
  return (
    <ToastProvider closeLabel={t("close")}>
      <a
        href="#main"
        onClick={(e) => {
          e.preventDefault();
          mainRef.current?.focus();
        }}
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[var(--z-skip)] focus:rounded-ctl focus:border-2 focus:border-ink focus:bg-paper focus:px-4 focus:py-3 focus:font-semibold focus:text-ink"
      >
        {t("skip")}
      </a>
      <Splash />
      <Navbar />
      <RouteEffects />
      <main id="main" tabIndex={-1} ref={mainRef} className="min-h-[60vh]">
        <Suspense
          fallback={
            <div className="grid min-h-[50vh] place-items-center">
              <Loader label={t("loading")} />
            </div>
          }
        >
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/schemes" element={<Schemes />} />
            <Route path="/about" element={<About />} />
            <Route path="/how-it-works" element={<HowItWorks />} />
            <Route path="/check-claim" element={<CheckClaim />} />
            <Route path="/action-plan" element={<ActionPlan />} />
            <Route path="/cases" element={<Cases />} />
            <Route path="/evidence" element={<Evidence />} />
            <Route path="/privacy" element={<Privacy />} />
            <Route path="/help" element={<Help />} />
            <Route path="/results/:id" element={<Results />} />
            <Route path="/dev/components" element={<DevComponents />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </main>
      <Footer />
      <CompanionSlot />
    </ToastProvider>
  );
}
