import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "@/api";

export type ServiceState = "checking" | "ok" | "down" | "unknown";
interface Ctx {
  status: ServiceState;
  retry(): void;
}
const ServiceContext = createContext<Ctx>({ status: "unknown", retry() {} });
export const useService = () => useContext(ServiceContext);

/** The fonts the first screen needs. `document.fonts.load` resolves when they are really usable (or fails fast if missing). */
async function fontsReady(): Promise<void> {
  const fonts = typeof document !== "undefined" ? document.fonts : undefined;
  if (!fonts?.load) return;
  await Promise.allSettled([fonts.load('500 1rem "Fraunces"'), fonts.load('400 1rem "Source Sans 3"')]);
}

/**
 * Real initialisation, nothing else: wait for the first fonts and for GET /health. `ready` flips the moment both
 * settle, so the splash can never outlive the work it reports on. A failed health check is not fatal: the app opens,
 * reading pages still work, and the claim page says what to do.
 */
export function ServiceProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ServiceState>("checking");
  const [fonts, setFonts] = useState(false);
  const run = useRef(0);

  const probe = useCallback(() => {
    const mine = ++run.current;
    setStatus("checking");
    api
      .health()
      .then((h) => mine === run.current && setStatus(h?.status === "ok" ? "ok" : "down"))
      .catch(() => mine === run.current && setStatus("down"));
  }, []);

  useEffect(() => {
    probe();
    void fontsReady().then(() => setFonts(true));
  }, [probe]);

  const value = useMemo(() => ({ status, retry: probe, ready: fonts && status !== "checking" }), [status, probe, fonts]);
  return <ReadyContext.Provider value={value.ready}><ServiceContext.Provider value={value}>{children}</ServiceContext.Provider></ReadyContext.Provider>;
}

const ReadyContext = createContext(true);
/** False only while the first fonts or the health check are still in flight. Defaults to true outside the provider. */
export const useAppReady = () => useContext(ReadyContext);
