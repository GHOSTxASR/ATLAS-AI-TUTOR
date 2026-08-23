import { useState } from "react";
import { FileWarning, Files, Loader2, Sparkles } from "lucide-react";
import { DocumentListItem } from "../components/documents/DocumentListItem";
import { DocumentUploadZone } from "../components/documents/DocumentUploadZone";
import {
  extractErrorMessage,
  useDeleteDocument,
  useDocuments,
  useReprocessDocument,
  useUploadDocument,
} from "../hooks/useDocuments";
import { useProfileStore } from "../stores/profileStore";
import { Document } from "../types";
import { CardSkeleton, EmptyState, ErrorState } from "../components/common/LoadingStates";

export function DocumentsPage() {
  const { activeProfileId } = useProfileStore();
  const documentsQuery = useDocuments(activeProfileId);
  const uploadMutation = useUploadDocument(activeProfileId);
  const deleteMutation = useDeleteDocument(activeProfileId);
  const reprocessMutation = useReprocessDocument(activeProfileId);

  const [uploadErrors, setUploadErrors] = useState<string[]>([]);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [pendingReprocessId, setPendingReprocessId] = useState<string | null>(null);
  const [markAsSyllabus, setMarkAsSyllabus] = useState(false);

  if (!activeProfileId) {
    return (
      <div className="flex h-full items-center justify-center p-8 py-20">
        <EmptyState
          icon={Files}
          title="No Active Profile Selected"
          description="Please select or create a profile to manage documents and syllabus files."
        />
      </div>
    );
  }

  const handleFilesSelected = async (files: File[]) => {
    setUploadErrors([]);
    const errors: string[] = [];

    for (const file of files) {
      try {
        await uploadMutation.mutateAsync({ file, isSyllabus: markAsSyllabus });
      } catch (err) {
        errors.push(`${file.name}: ${extractErrorMessage(err, "Upload failed.")}`);
      }
    }

    if (errors.length > 0) setUploadErrors(errors);
  };

  const handleDelete = async (document: Document) => {
    if (!window.confirm(`Delete "${document.filename}"? This cannot be undone.`)) return;
    setPendingDeleteId(document.id);
    try {
      await deleteMutation.mutateAsync(document.id);
    } catch (err) {
      setUploadErrors([extractErrorMessage(err, "Failed to delete document.")]);
    } finally {
      setPendingDeleteId(null);
    }
  };

  const handleReprocess = async (document: Document) => {
    setPendingReprocessId(document.id);
    try {
      await reprocessMutation.mutateAsync(document.id);
    } catch (err) {
      setUploadErrors([extractErrorMessage(err, "Failed to reprocess document.")]);
    } finally {
      setPendingReprocessId(null);
    }
  };

  const documents = documentsQuery.data ?? [];

  return (
    <div className="w-full min-w-0 space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 min-w-0">
          <div className="p-2.5 rounded-lg bg-primary-container/40 text-luminous-highlight border border-glass-border shadow-[0_0_10px_rgba(var(--accent-rgb),0.2)]">
            <Files className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-editorial text-3xl sm:text-4xl text-on-surface tracking-tight">
              Document Library
            </h1>
            <p className="text-xs sm:text-sm text-on-surface-variant font-sans mt-0.5">
              Upload textbook chapters, syllabi, lecture notes, and diagrams. Text & OCR are automatically extracted and indexed.
            </p>
          </div>
        </div>
      </div>

      {/* Upload Zone */}
      <div className="glass-panel p-6 rounded-2xl border border-glass-border shadow-[0_4px_30px_rgba(0,0,0,0.1)]">
        <DocumentUploadZone onFilesSelected={handleFilesSelected} isUploading={uploadMutation.isPending} />
        <label className="flex items-center gap-2 mt-3 text-xs text-on-surface-variant cursor-pointer">
          <input
            type="checkbox"
            checked={markAsSyllabus}
            onChange={(e) => setMarkAsSyllabus(e.target.checked)}
            className="rounded border-glass-border bg-surface-container/50 text-primary focus:ring-primary"
          />
          <span>Mark uploaded files as <strong className="text-on-surface">Syllabus</strong> documents</span>
        </label>
      </div>

      {uploadErrors.length > 0 && (
        <div role="alert" className="space-y-1 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs font-semibold text-rose-300">
          {uploadErrors.map((message, index) => (
            <p key={index}>{message}</p>
          ))}
        </div>
      )}

      {/* Documents List */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-editorial text-2xl text-on-surface">Uploaded Materials</h2>
          <span className="text-xs font-mono text-on-surface-variant bg-surface-container-high/60 border border-glass-border px-2 py-0.5 rounded">
            {documents.length} files
          </span>
        </div>

        {documentsQuery.isError ? (
          <ErrorState message={extractErrorMessage(documentsQuery.error, "Failed to load documents.")} onRetry={() => documentsQuery.refetch()} />
        ) : documentsQuery.isLoading ? (
          <CardSkeleton count={3} />
        ) : documents.length === 0 ? (
          <div className="glass-panel p-10 text-center rounded-2xl border border-glass-border text-xs text-on-surface-variant font-sans">
            No documents uploaded yet. Drag and drop PDF, DOCX, TXT or image files above.
          </div>
        ) : (
          <div className="space-y-3">
            {documents.map((doc) => (
              <DocumentListItem
                key={doc.id}
                document={doc}
                isDeleting={pendingDeleteId === doc.id}
                isReprocessing={pendingReprocessId === doc.id}
                onDelete={() => handleDelete(doc)}
                onReprocess={() => handleReprocess(doc)}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
