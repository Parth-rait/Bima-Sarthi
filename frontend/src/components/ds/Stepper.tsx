import { cn } from "@/lib/utils";

/**
 * Progress through a fixed sequence. Not links: the claim flow is gated, so a step you have not earned cannot be opened.
 * The current step is aria-current="step"; finished steps carry a tick glyph and a distinct outline (never colour alone).
 */
export function Stepper({ steps, current, label }: { steps: Array<{ id: string; text: string }>; current: string; label: string }) {
  const idx = steps.findIndex((s) => s.id === current);
  return (
    <nav aria-label={label}>
      <ol className="m-0 flex list-none gap-1 p-0">
        {steps.map((s, i) => {
          const state = i < idx ? "done" : i === idx ? "current" : "todo";
          return (
            <li
              key={s.id}
              aria-current={state === "current" ? "step" : undefined}
              data-state={state}
              className={cn(
                "flex min-h-11 min-w-0 flex-1 items-center justify-center gap-1.5 rounded-t-[var(--radius-tab)] border border-b-0 px-2 py-2 text-center text-control font-semibold",
                state === "current" && "border-ink bg-paper text-ink",
                state === "done" && "border-line-strong bg-peach text-ink",
                state === "todo" && "border-line bg-ivory text-ink-soft",
              )}
            >
              {state === "done" ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
                  <path d="m5 12.5 4.5 4.5L19 7.5" />
                </svg>
              ) : null}
              {s.text}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
