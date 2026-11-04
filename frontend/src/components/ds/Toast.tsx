import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { IconX } from "@/components/icons";

type Tone = "info" | "done";
interface ToastItem {
  id: number;
  text: string;
  tone: Tone;
}
interface ToastApi {
  push(text: string, tone?: Tone): void;
}
const Ctx = createContext<ToastApi>({ push() {} });
export const useToast = () => useContext(Ctx);

const AUTO_DISMISS_MS = 6000;

function Item({ item, closeLabel, onClose }: { item: ToastItem; closeLabel: string; onClose: (id: number) => void }) {
  useEffect(() => {
    const id = setTimeout(() => onClose(item.id), AUTO_DISMISS_MS);
    return () => clearTimeout(id);
  }, [item.id, onClose]);
  return (
    <li className="pointer-events-auto flex items-start gap-3 rounded-ctl border border-line bg-paper px-4 py-3 text-ink shadow-lift">
      <span aria-hidden="true" className="mt-1 inline-block size-2.5 shrink-0 rotate-45 bg-gold" />
      <span className="grow">{item.text}</span>
      <button type="button" onClick={() => onClose(item.id)} aria-label={closeLabel} className="-my-2 -mr-2 grid size-11 shrink-0 cursor-pointer place-items-center bg-transparent text-ink hover:bg-peach">
        <IconX size={18} />
      </button>
    </li>
  );
}

/** Short, polite confirmations ("Saved"). Never the only place an error is shown: errors stay inline. */
export function ToastProvider({ children, closeLabel }: { children: ReactNode; closeLabel: string }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const close = useCallback((id: number) => setItems((cur) => cur.filter((x) => x.id !== id)), []);
  const push = useCallback((text: string, tone: Tone = "info") => setItems((cur) => [...cur.slice(-2), { id: Date.now() + Math.random(), text, tone }]), []);
  const api = useMemo(() => ({ push }), [push]);
  return (
    <Ctx.Provider value={api}>
      {children}
      <ul role="status" aria-live="polite" className="no-print pointer-events-none fixed inset-x-4 bottom-4 z-[var(--z-toast)] m-0 flex max-w-sm list-none flex-col gap-2 p-0 sm:left-auto sm:right-4">
        {items.map((it) => (
          <Item key={it.id} item={it} closeLabel={closeLabel} onClose={close} />
        ))}
      </ul>
    </Ctx.Provider>
  );
}
