import { useId, useRef } from "react";
import { useSession } from "../state/store";
import { IconCamera, IconUpload } from "./icons";

const ACCEPT = ".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf";

/** Choose files, or take a photo on a phone. Chosen files are listed and can be removed before sending. */
export function FilePicker({
  files,
  onChange,
  label,
  inputId,
  disabled,
}: {
  files: File[];
  onChange: (files: File[]) => void;
  label: string;
  inputId?: string;
  disabled?: boolean;
}) {
  const { t } = useSession();
  const auto = useId();
  const id = inputId ?? auto;
  const pick = useRef<HTMLInputElement>(null);
  const cam = useRef<HTMLInputElement>(null);
  const add = (list: FileList | null, el: HTMLInputElement | null) => {
    if (list && list.length) onChange([...files, ...Array.from(list)]);
    if (el) el.value = "";
  };
  return (
    <div className="picker">
      <label htmlFor={id}>{label}</label>
      <div className="picker-row">
        <input
          ref={pick}
          id={id}
          className="file-input"
          type="file"
          accept={ACCEPT}
          multiple
          disabled={disabled}
          onChange={(e) => add(e.target.files, pick.current)}
        />
        <input
          ref={cam}
          id={`${id}-cam`}
          className="sr-only-input"
          type="file"
          accept="image/*"
          capture="environment"
          disabled={disabled}
          onChange={(e) => add(e.target.files, cam.current)}
        />
        <label className="btn secondary with-icon camera" htmlFor={`${id}-cam`}>
          <IconCamera />
          <span>{t("take_photo")}</span>
        </label>
      </div>
      <div className="picked" aria-label={t("files_selected")}>
        {files.length === 0 ? (
          <p className="hint">{t("no_files")}</p>
        ) : (
          <ul>
            {files.map((f, i) => (
              <li key={`${f.name}-${f.size}-${i}`}>
                <IconUpload />
                <span className="fname">{f.name}</span>
                <button type="button" className="quiet" onClick={() => onChange(files.filter((_, j) => j !== i))}>
                  {t("remove")}
                  <span className="sr-only"> {f.name}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
