import { cn } from "@/lib/utils";
import { useSession } from "@/state/store";

export interface SegOption {
  id: string;
  text: string;
  pressed: boolean;
  onClick: () => void;
  lang?: string;
}

/** A two-way switch built from real toggle buttons (aria-pressed). The pressed one is filled ink (light surfaces) or ivory (ink band). */
export function Seg({ label, options, className, tone = "light" }: { label: string; options: SegOption[]; className?: string; tone?: "light" | "ink" | "night" }) {
  const onInk = tone !== "light";
  return (
    <div role="group" aria-label={label} className={cn("inline-flex overflow-hidden rounded-ctl border", onInk ? "border-on-ink-soft" : "border-line-strong", className)}>
      {options.map((o, i) => (
        <button
          key={o.id}
          type="button"
          id={o.id}
          lang={o.lang}
          aria-pressed={o.pressed}
          onClick={o.onClick}
          className={cn(
            "min-h-11 cursor-pointer whitespace-nowrap px-3 text-control transition-colors duration-150 motion-reduce:transition-none",
            i > 0 && (onInk ? "border-l border-on-ink-soft" : "border-l border-line-strong"),
            onInk
              ? o.pressed ? "bg-on-ink font-bold text-ink" : "bg-transparent font-medium text-on-ink hover:bg-ink-raised"
              : o.pressed ? "bg-action font-bold text-on-ink" : "bg-transparent font-medium text-ink hover:bg-peach",
          )}
        >
          {o.text}
        </button>
      ))}
    </div>
  );
}

export function LangToggle({ idPrefix = "", className }: { idPrefix?: string; className?: string }) {
  const { state, actions, t } = useSession();
  return (
    <Seg
      className={className}
      label={t("lang_group")}
      options={[
        { id: `${idPrefix}lang-en`, text: "English", pressed: state.lang === "en", onClick: () => actions.setLang("en"), lang: "en" },
        { id: `${idPrefix}lang-hi`, text: "हिन्दी", pressed: state.lang === "hi", onClick: () => actions.setLang("hi"), lang: "hi" },
      ]}
    />
  );
}

export function RoleToggle({ idPrefix = "", className, tone }: { idPrefix?: string; className?: string; tone?: "light" | "ink" | "night" }) {
  const { state, actions, t } = useSession();
  return (
    <Seg
      tone={tone}
      className={className}
      label={t("role_group")}
      options={[
        { id: `${idPrefix}role-self`, text: t("self"), pressed: !state.helper, onClick: () => actions.setHelper(false) },
        { id: `${idPrefix}role-helper`, text: t("helper"), pressed: state.helper, onClick: () => actions.setHelper(true) },
      ]}
    />
  );
}
