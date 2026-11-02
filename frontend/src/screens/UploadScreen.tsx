import { useState } from "react";
import { ErrorBox } from "../components/ErrorBox";
import { Button } from "../components/ds/Button";
import { FileUploader, overLimit } from "../components/ds/FileUploader";
import { ProgressIndicator } from "../components/ds/ProgressIndicator";
import { describeError, type ViewError } from "../lib/errors";
import { useSession } from "../state/store";

export function UploadScreen() {
  const { state, actions, t } = useSession();
  const [files, setFiles] = useState<File[]>([]);
  const [err, setErr] = useState<ViewError | null>(null);
  const busy = state.busy === "extract" || state.busy === "session";

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setErr(null);
    if (!files.length || overLimit(files)) return;
    const out = await actions.extract(files);
    if (!out.ok) setErr(describeError(out.error, t, (k) => k.replaceAll("_", " ")));
  };
  const manual = async () => {
    setErr(null);
    const out = await actions.startManual();
    if (!out.ok) setErr(describeError(out.error, t, (k) => k.replaceAll("_", " ")));
  };

  return (
    <section aria-labelledby="h-upload" className="screen">
      <h2 id="h-upload" tabIndex={-1} data-screen-heading>
        {t("up_h")}
      </h2>
      <p className="lede">{t("up_p")}</p>
      <form onSubmit={submit} className="stack">
        <FileUploader files={files} onChange={setFiles} label={t("up_l")} inputId="files" disabled={busy} />
        <div className="actions">
          <Button type="submit" size="lg" loading={busy} disabled={files.length === 0 || overLimit(files)}>
            {t("up_b")}
          </Button>
        </div>
        {busy ? <ProgressIndicator label={t("reading")} /> : null}
        <p role="status" className="status" aria-live="polite">
          {busy ? t("reading") : ""}
          {busy && state.slow ? ` ${t("slow")}` : ""}
        </p>
        {err ? (
          <ErrorBox message={err.message}>
            {err.canEnterManually ? (
              <p>
                <button type="button" className="secondary" onClick={manual}>
                  {t("manual")}
                </button>
              </p>
            ) : null}
          </ErrorBox>
        ) : null}
      </form>
    </section>
  );
}
