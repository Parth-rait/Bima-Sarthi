import { DraggableCardBody, DraggableCardContainer } from "@/components/ui/draggable-card";
import { Tag } from "@/components/ds/StatusBadge";
import { ART } from "@/content/art";
import { useSession } from "@/state/store";
import type { Scenario } from "@/content/scenarios";

const POS = ["left-0 top-8 rotate-[-3deg]", "left-[calc(50%-10rem)] top-16 rotate-[2deg]", "right-0 top-6 rotate-[4deg]"];

/**
 * The illustrative scenarios as a desk of loose cards (Aceternity DraggableCard). They are laid out side by side at rest,
 * so every card is fully readable without touching it; dragging is a nicety, and the same text is the only way the
 * scenarios appear on small screens and under reduced motion (the card then does not drag at all).
 */
export default function DraggableScenarios({ scenarios }: { scenarios: Scenario[] }) {
  const { t } = useSession();
  return (
    <DraggableCardContainer className="relative h-[34rem] overflow-hidden rounded-card">
      {scenarios.map((s, i) => (
        <DraggableCardBody key={s.id} className={`absolute min-h-0 w-[20rem] rounded-card border border-line bg-paper p-5 text-ink ${POS[i % POS.length]}`}>
          <Tag tone="brass">{t("cases_illustrative")}</Tag>
          <img src={ART[s.art]} alt={s.artAlt} width={280} height={160} className="pointer-events-none relative z-10 mt-3 h-36 w-full select-none object-cover" draggable={false} />
          <h3 className="mb-0 mt-4 font-display text-[1.25rem] font-medium leading-tight text-ink">{s.title}</h3>
          <p className="mb-0 mt-2 select-none text-[0.9375rem] leading-snug">{s.body}</p>
        </DraggableCardBody>
      ))}
    </DraggableCardContainer>
  );
}
