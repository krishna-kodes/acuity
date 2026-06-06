"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";

const ACCEPTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];
const MAX_BYTES = 10 * 1024 * 1024; // 10 MB

type UploadStatus = "idle" | "uploading" | "success" | "error";

function formatBytes(bytes: number) {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(1)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function FileTypeIcon({ type }: { type: string }) {
  const isPDF = type === "application/pdf";
  return (
    <div className={cn(
      "w-8 h-8 rounded-md flex items-center justify-center text-[10px] font-bold shrink-0",
      isPDF ? "bg-destructive-subtle text-destructive" : "bg-accent-subtle text-accent-foreground"
    )}>
      {isPDF ? "PDF" : "DOC"}
    </div>
  );
}

interface DropzoneProps {
  file: File | null;
  error: string | null;
  onFile: (file: File | null) => void;
}

function Dropzone({ file, error, onFile }: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const validate = useCallback((f: File): string | null => {
    if (!ACCEPTED_TYPES.includes(f.type)) return "Only PDF and DOCX files are accepted.";
    if (f.size > MAX_BYTES) return "File must be 10 MB or smaller.";
    return null;
  }, []);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (!dropped) return;
    const err = validate(dropped);
    if (err) { onFile(null); return; }
    onFile(dropped);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = e.target.files?.[0] ?? null;
    if (!picked) return;
    const err = validate(picked);
    if (err) { onFile(null); return; }
    onFile(picked);
  };

  if (file) {
    return (
      <div className="flex items-center gap-3 p-3 border border-border rounded-lg bg-surface-subtle">
        <FileTypeIcon type={file.type} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground truncate">{file.name}</p>
          <p className="text-xs text-text-muted">{formatBytes(file.size)}</p>
        </div>
        <button
          type="button"
          onClick={() => { onFile(null); if (inputRef.current) inputRef.current.value = ""; }}
          className="w-6 h-6 rounded flex items-center justify-center text-text-muted hover:text-destructive hover:bg-destructive-subtle transition-colors"
          aria-label="Remove file"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}>
            <path d="M2 2l10 10M12 2L2 12" strokeLinecap="round" />
          </svg>
        </button>
      </div>
    );
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={cn(
          "w-full flex flex-col items-center gap-3 p-8 rounded-lg border-2 border-dashed transition-colors",
          dragging
            ? "border-primary bg-accent-subtle"
            : error
            ? "border-destructive/50 bg-destructive-subtle/40"
            : "border-border hover:border-primary/50 hover:bg-surface-subtle"
        )}
      >
        <div className="w-10 h-10 rounded-xl bg-surface-subtle border border-border flex items-center justify-center">
          <svg className="w-5 h-5 text-text-muted" fill="none" viewBox="0 0 20 20" stroke="currentColor" strokeWidth={1.5}>
            <path d="M10 13V4M6 8l4-4 4 4" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M3 16h14" strokeLinecap="round" />
          </svg>
        </div>
        <div className="text-center">
          <p className="text-sm font-medium text-foreground">
            {dragging ? "Drop to upload" : "Drag & drop your requirements document"}
          </p>
          <p className="text-xs text-text-muted mt-1">or <span className="text-primary underline underline-offset-2">click to browse</span></p>
          <p className="text-xs text-text-muted mt-2">PDF or DOCX · max 10 MB</p>
        </div>
      </button>
      {error && (
        <p className="text-xs text-destructive mt-2 flex items-center gap-1">
          <svg className="w-3 h-3 shrink-0" fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2}>
            <circle cx="6" cy="6" r="5" />
            <path d="M6 4v3M6 8.5v.5" strokeLinecap="round" />
          </svg>
          {error}
        </p>
      )}
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx"
        className="sr-only"
        onChange={handleChange}
        tabIndex={-1}
      />
    </div>
  );
}

export default function NewProjectPage() {
  const router = useRouter();
  const [name, setName]         = useState("");
  const [domain, setDomain]     = useState("");
  const [file, setFile]         = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [status, setStatus]     = useState<UploadStatus>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleFile = (f: File | null) => {
    setFile(f);
    setFileError(f === null && file !== null ? "Only PDF and DOCX files are accepted." : null);
  };

  const canSubmit = name.trim().length > 0 && file !== null && status === "idle";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setStatus("uploading");
    setErrorMsg(null);

    try {
      // TODO (Epic 4): POST /api/v1/projects → { id } then POST /api/v1/projects/{id}/documents
      // Simulated upload delay until API is wired
      await new Promise((res) => setTimeout(res, 1500));
      setStatus("success");
      setTimeout(() => router.push("/"), 800);
    } catch {
      setStatus("error");
      setErrorMsg("Upload failed. Please try again.");
    }
  };

  if (status === "success") {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <div className="w-10 h-10 rounded-full bg-success-subtle border border-success/20 flex items-center justify-center">
          <svg className="w-5 h-5 text-success" fill="none" viewBox="0 0 20 20" stroke="currentColor" strokeWidth={2}>
            <path d="M4 10l5 5 7-8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <p className="text-sm font-medium text-foreground">Project created — redirecting…</p>
      </div>
    );
  }

  return (
    <div className="px-6 py-8 max-w-xl mx-auto">
      <form onSubmit={handleSubmit} className="flex flex-col gap-5">

        {/* Project name */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-foreground" htmlFor="proj-name">
            Project name <span className="text-destructive">*</span>
          </label>
          <input
            id="proj-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. E-Commerce Platform Rewrite"
            required
            className={cn(
              "w-full px-3 py-2 rounded-md border text-sm bg-background text-foreground",
              "placeholder:text-text-muted",
              "focus:outline-none focus:ring-2 focus:ring-ring",
              "border-border"
            )}
          />
        </div>

        {/* Domain / industry */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-foreground" htmlFor="proj-domain">
            Domain / industry
            <span className="text-text-muted font-normal ml-1">(optional)</span>
          </label>
          <input
            id="proj-domain"
            type="text"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder="e.g. Retail, FinTech, Healthcare"
            className={cn(
              "w-full px-3 py-2 rounded-md border text-sm bg-background text-foreground",
              "placeholder:text-text-muted",
              "focus:outline-none focus:ring-2 focus:ring-ring",
              "border-border"
            )}
          />
        </div>

        {/* File upload */}
        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-semibold text-foreground">
            Requirements document <span className="text-destructive">*</span>
          </span>
          <Dropzone file={file} error={fileError} onFile={handleFile} />
        </div>

        {/* Error */}
        {errorMsg && (
          <p className="text-xs text-destructive flex items-center gap-1.5">
            <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}>
              <circle cx="7" cy="7" r="6" />
              <path d="M7 4.5v3.5M7 9.5v.5" strokeLinecap="round" />
            </svg>
            {errorMsg}
          </p>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={!canSubmit}
          className={cn(
            "flex items-center justify-center gap-2 w-full py-2.5 rounded-md text-sm font-medium transition-colors",
            canSubmit
              ? "bg-primary text-primary-foreground hover:bg-accent-hover"
              : "bg-muted text-text-muted cursor-not-allowed"
          )}
        >
          {status === "uploading" ? (
            <>
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                <path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" />
              </svg>
              Uploading…
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2.5}>
                <path d="M7 2v10M2 7h10" strokeLinecap="round" />
              </svg>
              Create Project
            </>
          )}
        </button>

      </form>
    </div>
  );
}
