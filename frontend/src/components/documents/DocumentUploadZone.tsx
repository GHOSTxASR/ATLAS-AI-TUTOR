import { useRef, useState } from "react";
import { Loader2, UploadCloud } from "lucide-react";

interface DocumentUploadZoneProps {
  onFilesSelected: (files: File[]) => void;
  isUploading: boolean;
}

const ACCEPTED_EXTENSIONS = ".pdf,.docx,.txt,.png,.jpg,.jpeg,.webp,.gif,.bmp,.tiff";

export function DocumentUploadZone({ onFilesSelected, isUploading }: DocumentUploadZoneProps) {
  const [isDragActive, setIsDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    onFilesSelected(Array.from(fileList));
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Upload documents"
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragActive(true);
      }}
      onDragLeave={() => setIsDragActive(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsDragActive(false);
        handleFiles(e.dataTransfer.files);
      }}
      className={`flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed p-8 sm:p-10 text-center cursor-pointer transition-all focus-visible:ring-2 focus-visible:ring-primary ${
        isDragActive
          ? "border-primary bg-primary-container/20 shadow-[0_0_15px_rgba(var(--accent-rgb),0.15)]"
          : "border-glass-border bg-surface-container/30 hover:border-primary/60 hover:bg-surface-container/50"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED_EXTENSIONS}
        className="hidden"
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = "";
        }}
      />
      {isUploading ? (
        <Loader2 className="w-10 h-10 text-primary animate-spin" />
      ) : (
        <div className="p-3 bg-primary-container/30 text-primary rounded-2xl">
          <UploadCloud className="w-8 h-8" />
        </div>
      )}
      <div>
        <p className="text-xs sm:text-sm font-bold text-on-surface">
          {isUploading ? "Uploading & Extracting..." : "Drop files here or click to browse"}
        </p>
        <p className="text-[11px] text-on-surface-variant mt-1">
          PDF, DOCX, TXT, or scanned images. Text & OCR extracted automatically.
        </p>
      </div>
    </div>
  );
}
