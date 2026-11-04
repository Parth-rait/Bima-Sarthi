import { useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useFocusTrap } from "@/hooks/useFocusTrap";
import { IconX } from "@/components/icons";

/**
 * A modal dialog for decisions that need protected focus (confirming a deletion). Focus is trapped,
 * Escape and the close button dismiss it, focus returns to the control that opened it.
 * Use it sparingly: a task that needs no interruption should not be a modal.
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  closeLabel,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  closeLabel: string;
  children?: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const tid = useId();
  const did = useId();
  useFocusTrap(ref, open, onClose);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[var(--z-modal)] grid place-items-center bg-ink/70 p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={tid}
        aria-describedby={description ? did : undefined}
        tabIndex={-1}
        className="relative w-full max-w-md rounded-ctl border border-line bg-paper p-6 text-ink shadow-stage"
      >
        <button type="button" onClick={onClose} aria-label={closeLabel} className="absolute right-2 top-2 grid size-11 cursor-pointer place-items-center rounded-ctl bg-transparent text-ink hover:bg-peach">
          <IconX size={22} />
        </button>
        <h2 id={tid} className="pr-10 font-display text-[1.5rem] font-medium leading-tight text-ink">
          {title}
        </h2>
        {description ? (
          <p id={did} className="mt-3">
            {description}
          </p>
        ) : null}
        <div className="mt-6 flex flex-wrap gap-3">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
