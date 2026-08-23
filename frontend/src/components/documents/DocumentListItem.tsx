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
  pending: { label: "Pending", className: "bg-surface-container-high text-on-surface-variant" },
  extracting: { label: "Extracting...", className: "bg-primary-container/30 text-primary animate-pulse" },
  extracted: { label: "Extracted", className: "bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300" },
  pending_ocr: { label: "Awaiting OCR", className: "bg-primary-container/40 text-luminous-highlight" },
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
  const statusInfo = STATUS_STYLES[document.status] ?? { label: document.status, className: "bg-surface-container-high text-on-surface-variant" };
  const Icon = document.file_type === "image" ? ImageIcon : FileText;
  const canReprocess = document.status === "error" || document.status === "pending_ocr";

  return (
    <div className="flex items-center gap-3 sm:gap-4 glass-card border border-glass-border p-4 hover:border-primary/40 transition">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center bg-surface-container-high text-on-surface-variant">
        <Icon className="h-5 w-5" />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate text-xs sm:text-sm font-bold text-on-surface">
            {document.filename}
          </p>
          {document.is_syllabus && (
            <span className="shrink-0 bg-primary-container/40 px-1.5 py-0.5 text-[9px] font-extrabold text-primary uppercase">
              Syllabus
            </span>
          )}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-on-surface-variant">
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
            className="p-2 text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition disabled:opacity-50"
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
          className="p-2 text-on-surface-variant hover:bg-rose-500/15 hover:text-rose-400 transition disabled:opacity-50"
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
