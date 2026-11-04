import { useEffect, useState } from "react";
import { ErrorBox } from "../components/ErrorBox";
import { Spark } from "@/components/ds/Spark";
import { Button } from "../components/ds/Button";
import { FileUploader, overLimit } from "../components/ds/FileUploader";
import { WorkStage, prefetchStage, type StageStep } from "../components/stage/WorkStage";
import { describeError, type ViewError } from "../lib/errors";
import { useSession } from "../state/store";

/** The two requests behind "Read my documents": a private session is opened (first time only), then the documents are read. */
const READ_STEPS: StageStep[] = [
  { id: "session", label: "stage_session", mode: "arrive" },
  { id: "extract", label: "stage_reading", mode: "reading" },
];

export function UploadScreen() {
  const { state, actions, t } = useSession();
  const [files, setFiles] = useState<File[]>([]);
  const [err, setErr] = useState<ViewError | null>(null);
  const busy = state.busy === "extract" || state.busy === "session";

  // a file is chosen: fetch the 3D stage now, so it is ready the moment reading starts
  useEffect(() => {
    if (files.length) prefetchStage();
  }, [files.length]);

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
          <Spark>
            <Button type="submit" size="lg" loading={busy} disabled={files.length === 0 || overLimit(files)}>
              {t("up_b")}
            </Button>
          </Spark>
        </div>
        {busy ? <WorkStage steps={READ_STEPS} current={state.busy ?? "extract"} slow={state.slow} /> : null}
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
