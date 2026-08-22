import { useState } from "react";
import { BookOpen, ChevronDown, FileText, Network, NotebookPen, Share2 } from "lucide-react";
import { Citation } from "../../types";

const SOURCE_ICONS: Record<string, typeof FileText> = {
  document: FileText,
  note: NotebookPen,
  memory: BookOpen,
  graph_node: Share2,
  chat_summary: Network,
};

function sourceLabel(citation: Citation): string {
  if (citation.source_type === "document") {
    return citation.page_number
      ? `${citation.filename}, p.${citation.page_number}`
      : citation.filename;
  }
  if (citation.source_type === "memory") return `Memory: ${citation.filename}`;
  if (citation.source_type === "note") return `Note: ${citation.filename}`;
  if (citation.source_type === "graph_node") return `Concept: ${citation.filename}`;
  return citation.filename;
}

/**
 * Shows which of the learner's own materials grounded a reply.
 *
 * The backend has always sent these, but nothing rendered them, so answers
 * drawn from uploaded documents looked indistinguishable from ones invented
 * from the model's own knowledge.
 */
export function CitationList({ citations }: { citations: Citation[] }) {
  const [expanded, setExpanded] = useState(false);

  if (!citations || citations.length === 0) return null;

  return (
    <div className="mt-3 pt-2.5 border-t border-glass-border/60">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        className="flex items-center gap-1.5 text-[11px] font-semibold text-on-surface-variant hover:text-primary transition"
      >
        <FileText className="w-3 h-3" />
        <span>
          {citations.length} source{citations.length === 1 ? "" : "s"}
        </span>
        <ChevronDown
          className={`w-3 h-3 transition-transform ${expanded ? "rotate-180" : ""}`}
        />
      </button>

      {expanded && (
        <ol className="mt-2 space-y-1.5">
          {citations.map((citation) => {
            const Icon = SOURCE_ICONS[citation.source_type] ?? FileText;
            return (
              <li
                key={`${citation.source_id}-${citation.index}`}
                className="flex gap-2 text-[11px] text-on-surface-variant"
              >
                <span className="font-mono text-primary shrink-0">[{citation.index}]</span>
                <div className="min-w-0">
                  <div className="flex items-center gap-1 text-on-surface font-medium">
                    <Icon className="w-3 h-3 shrink-0" />
                    <span className="truncate">{sourceLabel(citation)}</span>
                  </div>
                  {citation.snippet && (
                    <p className="mt-0.5 leading-snug opacity-80">{citation.snippet}</p>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
