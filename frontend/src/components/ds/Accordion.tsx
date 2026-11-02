import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { IconChevronDown } from "@/components/icons";
import { cn } from "@/lib/utils";

export interface AccordionItem {
  id: string;
  title: ReactNode;
  content: ReactNode;
}

/**
 * Accessible accordion (WAI-ARIA disclosure pattern): every header is a real button with
 * aria-expanded / aria-controls; Arrow Up/Down, Home and End move between headers.
 * Panels stay in the DOM (hidden) so find-in-page and the Help search can still reach their text.
 */
export function Accordion({
  items,
  multiple = true,
  defaultOpen = [],
  className,
}: {
  items: AccordionItem[];
  multiple?: boolean;
  defaultOpen?: string[];
  className?: string;
}) {
  const base = useId();
  const [open, setOpen] = useState<string[]>(defaultOpen);
  const heads = useRef<Array<HTMLButtonElement | null>>([]);

  const toggle = (id: string) =>
    setOpen((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : multiple ? [...cur, id] : [id]));

  const onKey = (e: KeyboardEvent, i: number) => {
    const n = items.length;
    const go = (j: number) => {
      e.preventDefault();
      heads.current[(j + n) % n]?.focus();
    };
    if (e.key === "ArrowDown") go(i + 1);
    else if (e.key === "ArrowUp") go(i - 1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(n - 1);
  };

  return (
    <div className={cn("divide-y divide-line border-y border-line", className)}>
      {items.map((it, i) => {
        const isOpen = open.includes(it.id);
        const hid = `${base}-h-${it.id}`;
        const pid = `${base}-p-${it.id}`;
        return (
          <div key={it.id}>
            <h3 className="m-0">
              <button
                ref={(el) => {
                  heads.current[i] = el;
                }}
                id={hid}
                type="button"
                aria-expanded={isOpen}
                aria-controls={pid}
                onClick={() => toggle(it.id)}
                onKeyDown={(e) => onKey(e, i)}
                className="flex min-h-14 w-full cursor-pointer items-center justify-between gap-4 bg-transparent px-1 py-3 text-left font-display text-[1.1875rem] font-medium text-ink hover:bg-peach"
              >
                <span>{it.title}</span>
                <IconChevronDown size={22} className={cn("shrink-0 transition-transform duration-200 motion-reduce:transition-none", isOpen && "rotate-180")} />
              </button>
            </h3>
            <div id={pid} role="region" aria-labelledby={hid} hidden={!isOpen} className="pb-5 pr-8 text-ink">
              {it.content}
            </div>
          </div>
        );
      })}
    </div>
  );
}
