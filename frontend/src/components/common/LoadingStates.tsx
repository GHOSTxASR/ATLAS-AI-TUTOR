import React from "react";
import { AlertCircle, RefreshCw, FolderOpen, Loader2 } from "lucide-react";

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className = "" }: SkeletonProps) {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="Loading content"
      className={`animate-pulse bg-surface-container-high/60 rounded-lg ${className}`}
    />
  );
}

export function CardSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" role="status" aria-label="Loading cards">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="p-5 glass-panel border border-glass-border rounded-2xl shadow-sm space-y-3"
        >
          <div className="flex items-center justify-between">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-6 w-6 rounded-full" />
          </div>
          <Skeleton className="h-8 w-20" />
          <Skeleton className="h-3 w-40" />
        </div>
      ))}
    </div>
  );
}

export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="w-full glass-panel border border-glass-border rounded-2xl overflow-hidden shadow-sm" role="status" aria-label="Loading table">
      <div className="p-4 bg-surface-container-high/40 border-b border-glass-border flex gap-4">
        {Array.from({ length: cols }).map((_, j) => (
          <Skeleton key={j} className="h-4 flex-1" />
        ))}
      </div>
      <div className="divide-y divide-glass-border">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="p-4 flex gap-4">
            {Array.from({ length: cols }).map((_, j) => (
              <Skeleton key={j} className="h-3.5 flex-1" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function Spinner({
  size = "md",
  className = "",
  label = "Loading...",
}: {
  size?: "sm" | "md" | "lg";
  className?: string;
  label?: string;
}) {
  const sizeMap = {
    sm: "w-4 h-4",
    md: "w-6 h-6",
    lg: "w-8 h-8",
  };

  return (
    <div className="inline-flex items-center justify-center" role="status" aria-label={label}>
      <Loader2 className={`animate-spin text-primary ${sizeMap[size]} ${className}`} />
      <span className="sr-only">{label}</span>
    </div>
  );
}

export function EmptyState({
  icon: Icon = FolderOpen,
  title,
  description,
  actionLabel,
  onAction,
}: {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="py-12 px-4 text-center flex flex-col items-center justify-center space-y-3 glass-panel border border-dashed border-glass-border rounded-2xl">
      <div className="p-3 bg-primary-container/30 rounded-2xl text-primary">
        <Icon className="w-8 h-8" />
      </div>
      <h3 className="text-base font-bold text-on-surface">{title}</h3>
      {description && <p className="text-xs text-on-surface-variant max-w-sm">{description}</p>}
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="mt-2 px-4 py-2 bg-primary hover:opacity-90 active:scale-95 text-on-primary text-xs font-semibold rounded-xl shadow-[0_0_10px_rgba(160,240,237,0.2)] transition"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
  actionLabel = "Retry",
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
  actionLabel?: string;
}) {
  return (
    <div
      role="alert"
      className="p-6 bg-rose-500/10 border border-rose-500/20 rounded-2xl text-center space-y-3"
    >
      <AlertCircle className="w-8 h-8 text-rose-400 mx-auto" />
      <h3 className="text-sm font-bold text-rose-300">{title}</h3>
      {message && <p className="text-xs text-rose-300/80 max-w-md mx-auto">{message}</p>}
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-rose-500/20 hover:bg-rose-500/30 active:scale-95 text-rose-300 border border-rose-500/30 text-xs font-semibold rounded-xl transition"
        >
          <RefreshCw className="w-3.5 h-3.5" /> {actionLabel}
        </button>
      )}
    </div>
  );
}
