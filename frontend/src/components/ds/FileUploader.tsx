import { IconCamera, IconFile, IconUpload } from "@/components/icons";
import { useEffect, useId, useRef, useState, type DragEvent } from "react";
import { useSession } from "@/state/store";
import { cn } from "@/lib/utils";
import { rowOrder } from "@/lib/motion";
import { buttonStyles } from "./Button";
import { ProgressIndicator } from "./ProgressIndicator";

/** What the backend accepts (sarthi/app/session.py): JPG, PNG, PDF; 25 MB in total; 20 pages in total. */
export const MAX_TOTAL_BYTES = 25 * 1024 * 1024;
export const ACCEPT = ".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf";
const EXTS = [".jpg", ".jpeg", ".png", ".pdf"];
const MIMES = ["image/jpeg", "image/png", "application/pdf"];

export type Rejection = { name: string; reason: "type" | "empty" };

export function isAccepted(f: File): boolean {
  const n = f.name.toLowerCase();
  return EXTS.some((e) => n.endsWith(e)) || MIMES.includes(f.type);
}
export const totalBytes = (files: File[]) => files.reduce((n, f) => n + f.size, 0);
export const overLimit = (files: File[]) => totalBytes(files) > MAX_TOTAL_BYTES;
export const formatSize = (b: number) => (b >= 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);

function Preview({ file }: { file: File }) {
  const [url, setUrl] = useState<string | null>(null);
  const image = file.type.startsWith("image/") || /\.(jpe?g|png)$/i.test(file.name);
  useEffect(() => {
    if (!image || typeof URL.createObjectURL !== "function") return;
    const u = URL.createObjectURL(file);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file, image]);
  return (
    <span aria-hidden="true" className="grid size-14 shrink-0 place-items-center overflow-hidden rounded-ctl border border-line bg-peach text-ink-soft">
      {url ? <img src={url} alt="" className="size-full object-cover" /> : <IconFile size={26} />}
    </span>
  );
}

/**
 * Choose, take, or drop files. Files are validated here the way the server will validate them
 * (type, 25 MB total); previews come from the browser (nothing is uploaded until the user presses the read button);
 * every file can be replaced or removed. There is NO upload percentage on purpose: the request is a single
 * `fetch`, the server reports none, so the busy state is an honest indeterminate "reading" message.
 */
export function FileUploader({
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
  const swap = useRef<HTMLInputElement>(null);
  const swapIndex = useRef(0);
  const [rejected, setRejected] = useState<Rejection[]>([]);
  const [dragging, setDragging] = useState(false);

  const addList = (list: FileList | File[] | null) => {
    const incoming = list ? Array.from(list) : [];
    if (!incoming.length) return;
    const ok: File[] = [];
    const bad: Rejection[] = [];
    for (const f of incoming) {
      if (!isAccepted(f)) bad.push({ name: f.name, reason: "type" });
      else if (f.size === 0) bad.push({ name: f.name, reason: "empty" });
      else ok.push(f);
    }
    setRejected(bad);
    if (ok.length) onChange([...files, ...ok]);
  };
  const reset = (el: HTMLInputElement | null) => {
    if (el) el.value = "";
  };
  const replaceAt = (list: FileList | null) => {
    const f = list?.[0];
    if (!f) return;
    if (!isAccepted(f)) return setRejected([{ name: f.name, reason: "type" }]);
    if (f.size === 0) return setRejected([{ name: f.name, reason: "empty" }]);
    setRejected([]);
    onChange(files.map((x, i) => (i === swapIndex.current ? f : x)));
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (!disabled) addList(e.dataTransfer?.files ?? null);
  };

  const used = totalBytes(files);
  const pct = Math.min(100, (used / MAX_TOTAL_BYTES) * 100);
  const tooBig = used > MAX_TOTAL_BYTES;
  const describedBy = `${id}-rules`;

  return (
    <div className="picker">
      <p className="m-0 mb-1 font-semibold text-ink">{label}</p>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        data-drop={dragging ? "drag" : "idle"}
        className="dropzone rounded-ctl border-2 p-4 md:p-5"
      >
        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={pick}
            id={id}
            className="peer sr-only"
            type="file"
            accept={ACCEPT}
            multiple
            disabled={disabled}
            aria-describedby={describedBy}
            onChange={(e) => {
              addList(e.target.files);
              reset(pick.current);
            }}
          />
          <label htmlFor={id} className={cn(buttonStyles({ variant: "primary" }), "m-0 cursor-pointer peer-focus-visible:outline peer-focus-visible:outline-3 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-focus-ring", disabled && "pointer-events-none opacity-60")}>
            <IconUpload size={20} />
            {t("choose_files")}
          </label>
          <input
            ref={cam}
            id={`${id}-cam`}
            className="peer sr-only"
            type="file"
            accept="image/*"
            capture="environment"
            disabled={disabled}
            onChange={(e) => {
              addList(e.target.files);
              reset(cam.current);
            }}
          />
          <label htmlFor={`${id}-cam`} className={cn(buttonStyles({ variant: "secondary" }), "camera m-0 cursor-pointer peer-focus-visible:outline peer-focus-visible:outline-3 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-focus-ring", disabled && "pointer-events-none opacity-60")}>
            <IconCamera size={20} />
            <span>{t("take_photo")}</span>
          </label>
          <span className="hidden text-ink-soft md:inline">{t("drop_here")}</span>
        </div>
        <p id={describedBy} className="mb-0 mt-3 text-control text-ink-soft">
          {t("up_rules")}
        </p>
      </div>

      {rejected.length ? (
        <div role="alert" className="mt-3 rounded-ctl border-2 border-terracotta bg-terracotta-wash p-4 text-terracotta-ink">
          <p className="m-0 font-bold">{t("fv_title")}</p>
          <ul className="mb-0 mt-2 list-disc pl-5">
            {rejected.map((r, i) => (
              <li key={`${r.name}-${i}`}>
                {r.name} {r.reason === "type" ? t("fv_type") : t("fv_empty")}
              </li>
            ))}
          </ul>
          <p className="mb-0 mt-2 font-semibold">{t("fv_next")}</p>
        </div>
      ) : null}

      <div className="picked mt-4" aria-label={t("files_selected")}>
        {files.length === 0 ? (
          <p className="hint m-0 text-ink-soft">{t("no_files")}</p>
        ) : (
          <>
            <ul className="picked-list m-0 list-none p-0">
              {files.map((f, i) => (
                <li key={`${f.name}-${f.size}-${i}`} style={rowOrder(i)} className="picked-file flex flex-wrap items-center gap-3 py-3">
                  <Preview file={f} />
                  <span className="min-w-0 flex-1">
                    <span className="fname block break-all font-semibold text-ink">{f.name}</span>
                    <span className="block text-meta text-ink-soft">{formatSize(f.size)}</span>
                  </span>
                  <button
                    type="button"
                    disabled={disabled}
                    className={buttonStyles({ variant: "quiet", size: "sm" })}
                    onClick={() => {
                      swapIndex.current = i;
                      swap.current?.click();
                    }}
                  >
                    {t("replace")}{" "}
                    <span className="sr-only">{f.name}</span>
                  </button>
                  <button type="button" disabled={disabled} className={buttonStyles({ variant: "quiet", size: "sm" })} onClick={() => onChange(files.filter((_, j) => j !== i))}>
                    {t("remove")}{" "}
                    <span className="sr-only">{f.name}</span>
                  </button>
                </li>
              ))}
            </ul>
            <input
              ref={swap}
              type="file"
              className="sr-only"
              tabIndex={-1}
              aria-hidden="true"
              accept={ACCEPT}
              onChange={(e) => {
                replaceAt(e.target.files);
                reset(swap.current);
              }}
            />
            <div className="mt-4">
              <p className="m-0 mb-1 text-control text-ink-soft">
                {t("allowance")}: {formatSize(used)} / 25 MB
              </p>
              <ProgressIndicator value={pct} label={t("allowance")} valueText={`${formatSize(used)} / 25 MB`} />
              {tooBig ? (
                <p role="alert" className="mb-0 mt-2 font-semibold text-terracotta-ink">
                  {t("fv_size")} {t("fv_size_next")}
                </p>
              ) : null}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
