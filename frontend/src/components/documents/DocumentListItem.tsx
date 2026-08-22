import { FileText, Image as ImageIcon, Loader2, RefreshCw, Trash2 } from "lucide-react";
import { Document, DocumentStatus } from "../../types";

interface DocumentListItemProps {
  document: Document;
  onDelete: (document: Document) => void;
  onReprocess: (document: Document) => void;
  isDeleting: boolean;
  isReprocessing: boolean;
}

const STATUS_STYLES: Record<DocumentStatus, { label: string; className: string }> = {
  pending: { label: "Pending", className: "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300" },
  extracting: { label: "Extracting...", className: "bg-primary-container/30 text-primary animate-pulse" },
  extracted: { label: "Extracted", className: "bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300" },
  pending_ocr: { label: "Awaiting OCR", className: "bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300" },
  error: { label: "Error", className: "bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300" },
};

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

export function DocumentListItem({
  document,
  onDelete,
  onReprocess,
  isDeleting,
  isReprocessing,
}: DocumentListItemProps) {
  const statusInfo = STATUS_STYLES[document.status] ?? { label: document.status, className: "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300" };
  const Icon = document.file_type === "image" ? ImageIcon : FileText;
  const canReprocess = document.status === "error" || document.status === "pending_ocr";

  return (
    <div className="flex items-center gap-3 sm:gap-4 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-2xs hover:border-slate-300 dark:hover:border-slate-700 transition">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
        <Icon className="h-5 w-5" />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate text-xs sm:text-sm font-bold text-slate-900 dark:text-white">
            {document.filename}
          </p>
          {document.is_syllabus && (
            <span className="shrink-0 rounded-md bg-cyan-100 dark:bg-cyan-950 px-1.5 py-0.5 text-[9px] font-extrabold text-cyan-800 dark:text-cyan-300 uppercase">
              Syllabus
            </span>
          )}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-slate-400">
          <span className="uppercase font-semibold">{document.file_type}</span>
          {document.page_count != null && <span>{document.page_count} pages</span>}
          {document.word_count != null && document.word_count > 0 && (
            <span>{document.word_count.toLocaleString()} words</span>
          )}
          <span>{formatDate(document.uploaded_at)}</span>
        </div>
        {document.error_message && (
          <p className="mt-1 text-xs text-rose-500 font-semibold">{document.error_message}</p>
        )}
      </div>

      <span
        className={`shrink-0 rounded-xl px-2.5 py-1 text-[10px] font-bold ${statusInfo.className}`}
      >
        {statusInfo.label}
      </span>

      <div className="flex shrink-0 items-center gap-1">
        {canReprocess && (
          <button
            type="button"
            aria-label="Retry processing"
            title="Retry processing"
            onClick={() => onReprocess(document)}
            disabled={isReprocessing}
            className="rounded-xl p-2 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white transition disabled:opacity-50"
          >
            {isReprocessing ? (
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
          </button>
        )}
        <button
          type="button"
          aria-label="Delete document"
          title="Delete document"
          onClick={() => onDelete(document)}
          disabled={isDeleting}
          className="rounded-xl p-2 text-slate-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 hover:text-rose-600 transition disabled:opacity-50"
        >
          {isDeleting ? (
            <Loader2 className="h-4 w-4 animate-spin text-rose-500" />
          ) : (
            <Trash2 className="h-4 w-4" />
          )}
        </button>
      </div>
    </div>
  );
}
