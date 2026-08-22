import { useEffect, useMemo, useRef, useState } from "react";
import { Check, Loader2, RefreshCw, Search, Sparkles, TriangleAlert } from "lucide-react";
import { ModelInfo } from "../../api/settings";

interface ModelPickerProps {
  value: string;
  onChange: (modelId: string) => void;
  models: ModelInfo[];
  source: "live" | "fallback";
  error?: string | null;
  loading?: boolean;
  onRefresh: () => void;
}

function formatContext(tokens?: number | null): string {
  if (!tokens) return "";
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(tokens % 1_000_000 ? 1 : 0)}M ctx`;
  if (tokens >= 1_000) return `${Math.round(tokens / 1000)}K ctx`;
  return `${tokens} ctx`;
}

/**
 * Combobox over the provider's current model list.
 *
 * The list is fetched live, because provider line-ups change constantly and a
 * hardcoded catalogue goes stale silently — it was still offering models the
 * provider had retired while hiding new free ones.
 *
 * The text field *is* the model id, so typing a name the list does not contain
 * is always valid. That keeps the manual path open when a model is brand new,
 * private, or the provider is unreachable.
 */
export function ModelPicker({
  value,
  onChange,
  models,
  source,
  error,
  loading = false,
  onRefresh,
}: ModelPickerProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [freeOnly, setFreeOnly] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const freeCount = useMemo(() => models.filter((m) => m.free).length, [models]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return models
      .filter((m) => (freeOnly ? m.free : true))
      .filter((m) => !q || m.id.toLowerCase().includes(q) || m.label.toLowerCase().includes(q))
      .slice(0, 80);
  }, [models, query, freeOnly]);

  useEffect(() => setActiveIndex(0), [query, freeOnly]);

  // Close when focus or the pointer leaves the control.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  const commit = (modelId: string) => {
    onChange(modelId);
    setQuery("");
    setOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (open && filtered[activeIndex]) commit(filtered[activeIndex].id);
      else setOpen(false);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div ref={containerRef} className="relative">
      <div className="flex items-center gap-2">
        <div className="relative flex-1 min-w-0">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant pointer-events-none" />
          <input
            type="text"
            role="combobox"
            aria-expanded={open}
            aria-autocomplete="list"
            aria-label="Model name"
            value={open ? query : value}
            placeholder={value || "Search or type a model id..."}
            onFocus={() => {
              setQuery("");
              setOpen(true);
            }}
            onChange={(e) => {
              setQuery(e.target.value);
              // Typing is manual entry: keep the field authoritative even when
              // nothing in the list matches.
              onChange(e.target.value);
              setOpen(true);
            }}
            onKeyDown={handleKeyDown}
            className="w-full pl-9 pr-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface placeholder:text-on-surface-variant/60 focus:outline-hidden focus:border-primary transition"
          />
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          title="Re-query the provider for its current models"
          className="shrink-0 p-2 rounded-lg bg-surface-container/50 border border-glass-border text-on-surface-variant hover:text-on-surface disabled:opacity-40 transition"
        >
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Provenance: never imply a stale list is authoritative. */}
      <div className="flex items-center flex-wrap gap-x-3 gap-y-1 mt-1.5 text-[10px] text-on-surface-variant">
        {source === "live" ? (
          <span className="inline-flex items-center gap-1 text-emerald-400">
            <Check className="w-3 h-3" />
            {models.length} models live
            {freeCount > 0 && ` · ${freeCount} free`}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-amber-300">
            <TriangleAlert className="w-3 h-3" />
            Offline list — {error || "could not reach the provider"}
          </span>
        )}
        {freeCount > 0 && (
          <button
            type="button"
            onClick={() => setFreeOnly((v) => !v)}
            className={`px-1.5 py-0.5 rounded border transition ${
              freeOnly
                ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                : "border-glass-border hover:text-on-surface"
            }`}
          >
            Free only
          </button>
        )}
        <span className="opacity-70">Any model id can be typed directly.</span>
      </div>

      {open && (
        <ul
          role="listbox"
          className="absolute z-30 mt-1 w-full max-h-72 overflow-y-auto rounded-lg border border-glass-border bg-surface-container-high/95 backdrop-blur-xl shadow-[0_8px_30px_rgba(0,0,0,0.35)]"
        >
          {filtered.length === 0 ? (
            <li className="px-3 py-3 text-[11px] text-on-surface-variant">
              No match. Press Escape to keep “{value}”.
            </li>
          ) : (
            filtered.map((m, i) => (
              <li key={m.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={m.id === value}
                  onMouseEnter={() => setActiveIndex(i)}
                  onClick={() => commit(m.id)}
                  className={`w-full text-left px-3 py-2 flex items-center gap-2 transition ${
                    i === activeIndex ? "bg-primary/15" : ""
                  }`}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block text-xs text-on-surface truncate">{m.id}</span>
                    {m.label !== m.id && (
                      <span className="block text-[10px] text-on-surface-variant truncate">
                        {m.label}
                      </span>
                    )}
                  </span>
                  {m.context_length ? (
                    <span className="text-[10px] font-mono text-on-surface-variant shrink-0">
                      {formatContext(m.context_length)}
                    </span>
                  ) : null}
                  {m.free && (
                    <span className="inline-flex items-center gap-0.5 text-[9px] font-mono uppercase bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-1 py-0.5 rounded shrink-0">
                      <Sparkles className="w-2.5 h-2.5" />
                      Free
                    </span>
                  )}
                  {m.id === value && <Check className="w-3.5 h-3.5 text-primary shrink-0" />}
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
