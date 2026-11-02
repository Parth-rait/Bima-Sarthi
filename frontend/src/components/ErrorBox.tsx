import type { ReactNode, Ref } from "react";
import { Notice } from "@/components/ds/Notice";

/** role="alert" error summary. Pass a ref to move focus to it when an error appears. */
export function ErrorBox({
  message,
  items,
  children,
  boxRef,
  className,
}: {
  message?: string | null;
  items?: string[];
  children?: ReactNode;
  boxRef?: Ref<HTMLDivElement>;
  className?: string;
}) {
  if (!message && !children) return null;
  return (
    <Notice tone="error" boxRef={boxRef} className={className}>
      {message ? <p className="err m-0 font-semibold text-terracotta-ink">{message}</p> : null}
      {items && items.length ? (
        <ul className="m-0 list-disc space-y-0.5 pl-5">
          {items.map((x, i) => (
            <li key={`${i}-${x}`}>{x}</li>
          ))}
        </ul>
      ) : null}
      {children}
    </Notice>
  );
}
