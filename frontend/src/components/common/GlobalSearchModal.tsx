import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useProfileStore } from "../../stores/profileStore";
import {
  searchApi,
  GlobalCategory,
  GlobalSearchResponse,
  GlobalSearchResultItem,
} from "../../api/search";
import {
  Search,
  MessageSquare,
  FileText,
  Files,
  Network,
  Route,
  Loader2,
  Command,
  X,
} from "lucide-react";
import { ErrorState } from "./LoadingStates";
import { useFocusTrap } from "../../hooks/useFocusTrap";

interface GlobalSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function GlobalSearchModal({ isOpen, onClose }: GlobalSearchModalProps) {
  const navigate = useNavigate();
  const { activeProfileId } = useProfileStore();

  const [query, setQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<GlobalSearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(isOpen, dialogRef, onClose);

  useEffect(() => {
    if (!isOpen) {
      setQuery("");
      setResults(null);
      setError(null);
      return;
    }

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (!activeProfileId || !query.trim()) {
      setResults(null);
      return;
    }

    const timer = setTimeout(() => {
      setLoading(true);
      setError(null);
      searchApi
        .globalSearch(activeProfileId, query.trim(), {
          limit: 5,
          include_semantic: true,
          categories:
            selectedCategory === "all"
              ? undefined
              : [selectedCategory as GlobalCategory],
        })
        .then((res) => setResults(res))
        .catch((err) => setError(err?.response?.data?.error?.message || "Search failed. Please try again."))
        .finally(() => setLoading(false));
    }, 200);

    return () => clearTimeout(timer);
  }, [query, selectedCategory, activeProfileId, retryKey]);

  if (!isOpen) return null;

  const getCategoryIcon = (category: GlobalCategory) => {
    switch (category) {
      case "chats":
        return <MessageSquare className="w-4 h-4 text-primary" />;
      case "notes":
        return <FileText className="w-4 h-4 text-amber-300" />;
      case "documents":
        return <Files className="w-4 h-4 text-emerald-400" />;
      case "graph":
        return <Network className="w-4 h-4 text-cyan-300" />;
      case "roadmap":
        return <Route className="w-4 h-4 text-secondary" />;
    }
  };

  const handleNavigate = (path: string) => {
    onClose();
    navigate(path);
  };

  const allItems: GlobalSearchResultItem[] = results
    ? [
        ...(results.chats || []),
        ...(results.notes || []),
        ...(results.documents || []),
        ...(results.graph || []),
        ...(results.roadmap || []),
      ]
    : [];

  return (
    <div
      className="fixed inset-0 bg-black/70 backdrop-blur-md flex items-start justify-center pt-16 sm:pt-24 p-4 z-50 transition-opacity"
      role="dialog"
      aria-modal="true"
      aria-label="Global Search Command Palette"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        className="glass-panel border border-glass-border rounded-2xl max-w-2xl w-full shadow-[0_20px_60px_rgba(0,0,0,0.4)] overflow-hidden flex flex-col max-h-[80vh] text-on-surface"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Search Input */}
        <div className="p-4 border-b border-glass-border flex items-center gap-3 bg-surface-container/30">
          <Search className="w-4 h-4 text-on-surface-variant" />
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search chats, notes, documents, graph, roadmap..."
            aria-label="Search learning assets"
            className="flex-1 bg-transparent text-on-surface placeholder:text-on-surface-variant/60 text-xs sm:text-sm outline-hidden font-sans"
          />
          {loading && <Loader2 className="w-4 h-4 text-primary animate-spin" />}
          <kbd className="hidden sm:inline-block px-2 py-0.5 text-[10px] font-mono text-on-surface-variant bg-surface-container-high/60 border border-glass-border rounded">
            ESC
          </kbd>
          <button
            onClick={onClose}
            aria-label="Close search"
            className="p-1 text-on-surface-variant hover:text-on-surface sm:hidden"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Category Pills */}
        <div
          className="px-4 py-2.5 bg-surface-container/20 border-b border-glass-border flex gap-2 overflow-x-auto text-xs"
          role="tablist"
        >
          {[
            { id: "all", label: "All" },
            { id: "chats", label: "Chats 💬" },
            { id: "notes", label: "Notes 📝" },
            { id: "documents", label: "Documents 📄" },
            { id: "graph", label: "Graph 🕸️" },
            { id: "roadmap", label: "Roadmap 🗺️" },
          ].map((cat) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              role="tab"
              aria-selected={selectedCategory === cat.id}
              className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition ${
                selectedCategory === cat.id
                  ? "bg-primary text-on-primary shadow-[0_0_8px_rgba(160,240,237,0.3)]"
                  : "bg-surface-container/40 text-on-surface-variant hover:text-on-surface border border-glass-border"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Results List */}
        <div
          className="flex-1 overflow-y-auto p-4 space-y-2"
          role="region"
          aria-label="Search Results"
        >
          {query.trim() ? (
            error ? (
              <div className="p-6"><ErrorState message={error} onRetry={() => setRetryKey((value) => value + 1)} /></div>
            ) : allItems.length > 0 ? (
              allItems.map((item) => (
                <div
                  key={`${item.category}-${item.id}`}
                  onClick={() => handleNavigate(item.url_path)}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && handleNavigate(item.url_path)}
                  role="button"
                  className="p-3.5 rounded-xl bg-surface-container/30 hover:bg-surface-container/60 border border-glass-border hover:border-primary/40 cursor-pointer transition group focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {getCategoryIcon(item.category)}
                      <span className="font-semibold text-xs sm:text-sm text-on-surface group-hover:text-primary transition-colors">
                        {item.title}
                      </span>
                    </div>
                    <span className="text-[9px] font-mono font-semibold text-on-surface-variant uppercase tracking-wider bg-surface-container-high/60 border border-glass-border px-1.5 py-0.5 rounded">
                      {item.category}
                    </span>
                  </div>

                  {item.subtitle && (
                    <div className="text-xs text-primary font-medium mt-1 pl-6">
                      {item.subtitle}
                    </div>
                  )}

                  <div className="text-xs text-on-surface-variant mt-1 pl-6 line-clamp-2 leading-relaxed font-sans">
                    {item.snippet}
                  </div>
                </div>
              ))
            ) : !loading ? (
              <div className="text-center py-12 text-on-surface-variant text-xs font-sans">
                No matching results found for "{query}".
              </div>
            ) : null
          ) : (
            <div className="text-center py-12 text-on-surface-variant text-xs space-y-2 font-sans">
              <Command className="w-8 h-8 mx-auto text-on-surface-variant/40" />
              <div>Type to search across dialogues, notes, documents, concept atlas, and roadmaps.</div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2.5 bg-surface-container/40 border-t border-glass-border flex justify-between items-center text-[11px] text-on-surface-variant font-mono">
          <div>
            {results
              ? `${results.total_results} results found`
              : "Liquid Intelligence Omnisearch"}
          </div>
          <div className="flex gap-3">
            <span>
              Press <kbd className="font-mono">ESC</kbd> to close
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
