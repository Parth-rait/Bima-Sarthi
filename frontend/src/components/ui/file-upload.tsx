"use client";
import { cn } from "@/lib/utils";
import { useId, useRef, useState } from "react";
import { motion } from "motion/react";
import { IconUpload } from "@tabler/icons-react";
import { useDropzone } from "react-dropzone";

const mainVariant = {
  initial: {
    x: 0,
    y: 0,
  },
  animate: {
    x: 20,
    y: -20,
    opacity: 0.9,
  },
};

const secondaryVariant = {
  initial: {
    opacity: 0,
  },
  animate: {
    opacity: 1,
  },
};

/*
 * Aceternity "FileUpload" (registry @aceternity/file-upload-demo): react-dropzone, the hover animation, the file card
 * and the GridPattern are unchanged. Bima Sarthi changes (also in DESIGN.md): the drop area is keyboard-operable
 * (role="button", tabIndex 0, Enter/Space open the picker, visible focus ring) and the input has an accessible name; the
 * English strings are props (`title`, `hint`, `dropLabel`) so the claim flow can pass translated text; `accept` and
 * `multiple` are forwarded to the dropzone and the input; the white/neutral/dark: classes use our tokens; the dashed
 * sky-blue ghost box is a solid ink hairline; the stray console.log on rejected files is removed; the input id uses
 * useId (the original id was a constant, which breaks with two instances).
 * API: <FileUpload onChange={(files: File[]) => ...} title? hint? dropLabel? accept? multiple? />. onChange receives the
 * newly added files (not the accumulated list).
 * Phase 3b additions (claim workspace): `disabled` (no click, no drop, taken out of the tab order), `onReject(names)` (react-dropzone
 * silently drops files that do not match `accept`; the workspace needs to tell the person which and why), `showFiles={false}` (the
 * workspace owns the file list, with sizes, previews, remove and replace, so the component's own file cards and its internal list
 * are not shown; the upload tile stays), `className` (merged onto the drop area: the workspace halves the padding), a 2px ink ring
 * while a file is dragged over, and `describedBy` (ids of the rules text). Dropzone, hover motion, tile animation and GridPattern are untouched.
 */
export const FileUpload = ({
  onChange,
  title = "Upload file",
  hint = "Drag or drop your files here or click to upload",
  dropLabel = "Drop it",
  accept,
  multiple = false,
  disabled = false,
  onReject,
  showFiles = true,
  className,
  describedBy,
}: {
  onChange?: (files: File[]) => void;
  title?: string;
  hint?: string;
  dropLabel?: string;
  /** e.g. { "image/*": [], "application/pdf": [] } for the dropzone, plus the same list as an <input accept> string */
  accept?: { dropzone: Record<string, string[]>; input: string };
  multiple?: boolean;
  disabled?: boolean;
  /** names of the files react-dropzone refused because their type does not match `accept` */
  onReject?: (names: string[]) => void;
  /** false: the parent shows the list of chosen files; this component keeps only the upload tile */
  showFiles?: boolean;
  className?: string;
  describedBy?: string;
}) => {
  const [stored, setFiles] = useState<File[]>([]);
  const files = showFiles ? stored : [];
  const fileInputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();

  const handleFileChange = (newFiles: File[]) => {
    if (showFiles) setFiles((prevFiles) => [...prevFiles, ...newFiles]);
    onChange && onChange(newFiles);
  };

  const handleClick = () => {
    if (!disabled) fileInputRef.current?.click();
  };

  const { getRootProps, isDragActive } = useDropzone({
    multiple,
    accept: accept?.dropzone,
    noClick: true,
    noKeyboard: true,
    disabled,
    onDrop: (accepted) => {
      if (accepted.length) handleFileChange(accepted);
    },
    onDropRejected: (rejections) => onReject?.(rejections.map((r) => r.file.name)),
  });

  return (
    <div className="w-full" {...getRootProps()}>
      <motion.div
        onClick={handleClick}
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled || undefined}
        aria-describedby={describedBy}
        aria-label={`${title}. ${hint}`}
        onKeyDown={(e) => {
          if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            handleClick();
          }
        }}
        whileHover="animate"
        data-dragging={isDragActive ? "true" : undefined}
        className={cn(
          "group/file relative block w-full cursor-pointer overflow-hidden rounded-card bg-paper p-10",
          disabled && "cursor-not-allowed opacity-60",
          isDragActive && "ring-2 ring-ink",
          className,
        )}
      >
        <input
          ref={fileInputRef}
          id={inputId}
          type="file"
          tabIndex={-1}
          aria-hidden="true"
          accept={accept?.input}
          multiple={multiple}
          disabled={disabled}
          onChange={(e) => {
            const picked = Array.from(e.target.files || []);
            if (picked.length) handleFileChange(picked);
            e.target.value = "";
          }}
          className="hidden"
        />
        <div className="absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,white,transparent)]">
          <GridPattern />
        </div>
        <div className="flex flex-col items-center justify-center">
          <p className="relative z-20 font-sans text-base font-bold text-ink">
            {title}
          </p>
          <p className="relative z-20 mt-2 font-sans text-base font-normal text-ink-soft">
            {hint}
          </p>
          <div className="relative mx-auto mt-10 w-full max-w-xl">
            {files.length > 0 &&
              files.map((file, idx) => (
                <motion.div
                  key={"file" + idx}
                  layoutId={idx === 0 ? "file-upload" : "file-upload-" + idx}
                  className={cn(
                    "relative z-40 mx-auto mt-4 flex w-full flex-col items-start justify-start overflow-hidden rounded-ctl bg-ivory p-4 md:h-24",
                    "shadow-sm",
                  )}
                >
                  <div className="flex w-full items-center justify-between gap-4">
                    <motion.p
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      layout
                      className="max-w-xs truncate text-base text-ink"
                    >
                      {file.name}
                    </motion.p>
                    <motion.p
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      layout
                      className="shadow-input w-fit shrink-0 rounded-ctl px-2 py-1 text-sm text-ink-soft"
                    >
                      {(file.size / (1024 * 1024)).toFixed(2)} MB
                    </motion.p>
                  </div>

                  <div className="mt-2 flex w-full flex-col items-start justify-between text-sm text-ink-soft md:flex-row md:items-center">
                    <motion.p
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      layout
                      className="rounded-ctl bg-peach px-1 py-0.5"
                    >
                      {file.type}
                    </motion.p>

                    <motion.p
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      layout
                    >
                      modified{" "}
                      {new Date(file.lastModified).toLocaleDateString()}
                    </motion.p>
                  </div>
                </motion.div>
              ))}
            {!files.length && (
              <motion.div
                layoutId="file-upload"
                variants={mainVariant}
                transition={{
                  type: "spring",
                  stiffness: 300,
                  damping: 20,
                }}
                className={cn(
                  "relative z-40 mx-auto mt-4 flex h-32 w-full max-w-[8rem] items-center justify-center rounded-ctl bg-ivory group-hover/file:shadow-2xl",
                  "shadow-[0px_10px_50px_rgba(0,0,0,0.1)]",
                )}
              >
                {isDragActive ? (
                  <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex flex-col items-center text-ink-soft"
                  >
                    {dropLabel}
                    <IconUpload className="h-4 w-4 text-ink-soft" />
                  </motion.p>
                ) : (
                  <IconUpload className="h-4 w-4 text-ink-soft" />
                )}
              </motion.div>
            )}

            {!files.length && (
              <motion.div
                variants={secondaryVariant}
                className="absolute inset-0 z-30 mx-auto mt-4 flex h-32 w-full max-w-[8rem] items-center justify-center rounded-ctl border border-ink/40 bg-transparent opacity-0"
              ></motion.div>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export function GridPattern() {
  const columns = 41;
  const rows = 11;
  return (
    <div className="flex shrink-0 scale-105 flex-wrap items-center justify-center gap-x-px gap-y-px bg-peach">
      {Array.from({ length: rows }).map((_, row) =>
        Array.from({ length: columns }).map((_, col) => {
          const index = row * columns + col;
          return (
            <div
              key={`${col}-${row}`}
              className={`flex h-10 w-10 shrink-0 rounded-[2px] ${
                index % 2 === 0
                  ? "bg-ivory"
                  : "bg-ivory shadow-[0px_0px_1px_3px_rgba(255,255,255,1)_inset]"
              }`}
            />
          );
        }),
      )}
    </div>
  );
}
