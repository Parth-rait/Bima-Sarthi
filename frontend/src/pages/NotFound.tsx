import { Button } from "@/components/ds/Button";
import { EmptyState } from "@/components/ds/EmptyState";
import { Container } from "@/components/ds/Section";
import { ART } from "@/content/art";
import { useSession } from "@/state/store";

export default function NotFound() {
  const { t } = useSession();
  return (
    <Container className="py-16 md:py-24">
      <EmptyState
        pageHeading
        title={t("nf_title")}
        art={<img src={ART.folder} alt="" aria-hidden="true" width={220} height={220} className="w-44 rounded-ctl border border-line" />}
      >
        <p className="m-0">{t("nf_what")}</p>
        <p className="m-0">{t("nf_next")}</p>
        <div className="flex flex-wrap gap-3 pt-2">
          <Button to="/">{t("nav_home")}</Button>
          <Button to="/check-claim" variant="secondary">
            {t("nav_check")}
          </Button>
        </div>
      </EmptyState>
    </Container>
  );
}
