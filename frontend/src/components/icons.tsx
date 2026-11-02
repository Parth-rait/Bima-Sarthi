import type { Verdict } from "../api";

/** Drawn icons, one stroke weight (1.75) and one 24-unit grid. All decorative: names are in the adjacent text. */
const base = {
  width: 24,
  height: 24,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  focusable: false,
};
type IconProps = { size?: number; className?: string };
const sized = (size?: number) => ({ ...base, width: size ?? 24, height: size ?? 24 });

/** Verdict shapes: triangle, circle, square. Distinct silhouettes so colour is never the only signal. */
export function VerdictShape({ verdict }: { verdict: Verdict }) {
  if (verdict === "CHALLENGEABLE") {
    return (
      <svg {...base} className="verdict-shape">
        <path d="M12 3.5 21 19.5H3L12 3.5Z" fill="currentColor" fillOpacity={0.14} />
        <path d="M12 10v4.5" />
        <path d="M12 17.2v.01" />
      </svg>
    );
  }
  if (verdict === "NEED_INFO") {
    return (
      <svg {...base} className="verdict-shape">
        <circle cx="12" cy="12" r="8.5" fill="currentColor" fillOpacity={0.14} />
        <path d="M9.6 9.6a2.5 2.5 0 1 1 3.6 2.2c-.8.4-1.2.9-1.2 1.7" />
        <path d="M12 16.8v.01" />
      </svg>
    );
  }
  return (
    <svg {...base} className="verdict-shape">
      <rect x="4" y="4" width="16" height="16" rx="1.5" fill="currentColor" fillOpacity={0.14} />
      <path d="m8.6 12.4 2.4 2.4 4.6-5" />
    </svg>
  );
}

export function IconUpload({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <path d="M12 16V5" />
      <path d="m7.5 9.5 4.5-4.5 4.5 4.5" />
      <path d="M4.5 16.5v2.5h15v-2.5" />
    </svg>
  );
}
export function IconCamera({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <path d="M4 8.5h3l1.5-2.5h7L17 8.5h3v10H4v-10Z" />
      <circle cx="12" cy="13.2" r="3.2" />
    </svg>
  );
}
export function IconDownload({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <path d="M12 4v11" />
      <path d="m7.5 10.5 4.5 4.5 4.5-4.5" />
      <path d="M4.5 18.5h15" />
    </svg>
  );
}
export function IconPrint({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <path d="M7 9V4h10v5" />
      <path d="M7 17H4.5v-7h15v7H17" />
      <path d="M7 14h10v6H7z" />
    </svg>
  );
}
export function IconTrash({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <path d="M4.5 7h15" />
      <path d="M9.5 7V4.5h5V7" />
      <path d="m6.5 7 .8 12.5h9.4L17.5 7" />
    </svg>
  );
}
export function IconCheck({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </svg>
  );
}

export function IconChevronDown({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <path d="m6 9.5 6 6 6-6" />
    </svg>
  );
}
export function IconX({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}
export function IconMenu({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  );
}
export function IconArrowRight({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <path d="M4.5 12h15M14 6.5l5.5 5.5-5.5 5.5" />
    </svg>
  );
}
export function IconFile({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <path d="M6.5 3.5h7l4 4v13h-11z" />
      <path d="M13.5 3.5v4h4" />
      <path d="M9 13h6M9 16.5h6" />
    </svg>
  );
}
export function IconSearch({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <circle cx="10.5" cy="10.5" r="6" />
      <path d="m15 15 5 5" />
    </svg>
  );
}
export function IconExternal({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <path d="M13 4.5h6.5V11M19.5 4.5 11 13M17 14v5.5H5V7.5h5.5" />
    </svg>
  );
}

export function IconAlert({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <path d="M12 3.5 21 19.5H3L12 3.5Z" />
      <path d="M12 10v4.5M12 17.2v.01" />
    </svg>
  );
}
export function IconInfo({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 11v5M12 7.8v.01" />
    </svg>
  );
}
export function IconPencil({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <path d="m5 19 .8-3.6L16.2 5a1.9 1.9 0 0 1 2.7 2.7L8.5 18.2 5 19Z" />
      <path d="m14.5 6.8 2.7 2.7" />
    </svg>
  );
}
export function IconEye({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="2.8" />
    </svg>
  );
}
export function IconLock({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <rect x="5" y="10.5" width="14" height="9.5" rx="1.5" />
      <path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5" />
    </svg>
  );
}
export function IconRetry({ size, className }: IconProps) {
  return (
    <svg {...sized(size)} className={className}>
      <path d="M19.5 12a7.5 7.5 0 1 1-2.4-5.5" />
      <path d="M19.5 4.5v4h-4" />
    </svg>
  );
}
/** Status glyphs for fact badges: a square tick (verified), a diamond with a mark (please confirm), a tick in a circle (you confirmed). */
export function BadgeGlyph({ kind }: { kind: "verified" | "pending" | "confirmed" }) {
  if (kind === "verified") {
    return (
      <svg {...base} width={16} height={16} className="shrink-0">
        <path d="m5 12.5 4.5 4.5L19 7.5" />
      </svg>
    );
  }
  if (kind === "confirmed") {
    return (
      <svg {...base} width={16} height={16} className="shrink-0">
        <circle cx="12" cy="12" r="8.5" />
        <path d="m8.4 12.3 2.5 2.5 4.7-5" />
      </svg>
    );
  }
  return (
    <svg {...base} width={16} height={16} className="shrink-0">
      <path d="M12 3.5 20.5 12 12 20.5 3.5 12 12 3.5Z" />
      <path d="M12 8.5v4M12 15.4v.01" />
    </svg>
  );
}
