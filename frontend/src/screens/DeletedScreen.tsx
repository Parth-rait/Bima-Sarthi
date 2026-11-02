import { useSession } from "../state/store";

export function DeletedScreen() {
  const { actions, t } = useSession();
  return (
    <section aria-labelledby="h-deleted" className="screen">
      <h2 id="h-deleted" tabIndex={-1} data-screen-heading>
        {t("deleted_h")}
      </h2>
      <p role="status">{t("deleted")}</p>
      <div className="actions">
        <button type="button" onClick={() => actions.restart()}>
          {t("again")}
        </button>
      </div>
    </section>
  );
}
