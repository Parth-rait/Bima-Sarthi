import dossier from "@/assets/art/dossier-hero.svg";
import evidence from "@/assets/art/scene-evidence.svg";
import folder from "@/assets/art/scene-folder.svg";
import letter from "@/assets/art/scene-letter.svg";
import medical from "@/assets/art/scene-medical.svg";
import schedule from "@/assets/art/scene-schedule.svg";
import timeline from "@/assets/art/scene-timeline.svg";

/** Original artwork (frontend/src/assets/art). Imported so Vite emits hashed files under /assets, which FastAPI serves. */
export const ART = { dossier, evidence, folder, letter, medical, schedule, timeline } as const;
export type ArtKey = keyof typeof ART;
