import { useEffect, useState } from "react";
import { Loader2, Route, Sparkles } from "lucide-react";

import { documentsApi } from "../../api/documents";
import { roadmapApi } from "../../api/roadmap";
import { Document } from "../../types";
import { getErrorMessage } from "../../utils/errors";

type RoadmapMode = "strict" | "adaptive" | "hybrid";

const MODES: { id: RoadmapMode; label: string; blurb: string }[] = [
  { id: "strict", label: "Strict", blurb: "Follows the syllabus order exactly." },
  { id: "adaptive", label: "Adaptive", blurb: "Lets the model reorder by dependency." },
  { id: "hybrid", label: "Hybrid", blurb: "Keeps the structure, refines the ordering." },
];

interface GenerateRoadmapPanelProps {
  profileId: string;
  /** Whether a roadmap already exists, which changes what this warns about. */
  hasExistingRoadmap: boolean;
  onGenerated: () => void;
}

/**
 * Turning a syllabus into a roadmap.
 *
 * The API and its client wrapper both existed from the start, but nothing ever
 * called them: uploading a document and ticking "Mark as Syllabus" set a flag
 * that nothing downstream consumed, so a roadmap could not be created from the
 * interface at all. This is the missing step.
 */
export function GenerateRoadmapPanel({
  profileId,
  hasExistingRoadmap,
  onGenerated,
}: GenerateRoadmapPanelProps) {
  const [syllabi, setSyllabi] = useState<Document[]>([]);
  const [documentId, setDocumentId] = useState("");
  const [mode, setMode] = useState<RoadmapMode>("strict");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    documentsApi
      .getAll(profileId)
      .then((docs) => {
        if (cancelled) return;
        // Only a syllabus that finished indexing can be parsed into topics.
        const usable = docs.filter((d) => d.is_syllabus && d.status === "indexed");
        setSyllabi(usable);
        setDocumentId((current) => current || usable[0]?.id || "");
      })
      .catch((err) => {
        if (!cancelled) setError(getErrorMessage(err, "Could not load your documents."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [profileId]);

  const handleGenerate = async () => {
    if (!documentId) return;
    setGenerating(true);
    setError(null);
    try {
      await roadmapApi.generateRoadmap(profileId, {
        document_id: documentId,
        mode,
        title: syllabi.find((d) => d.id === documentId)?.filename.replace(/\.[^.]+$/, ""),
      });
      onGenerated();
    } catch (err) {
      setError(getErrorMessage(err, "Could not generate the roadmap."));
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-center text-xs text-on-surface-variant font-sans">
        <Loader2 className="w-4 h-4 animate-spin inline mr-2" />
        Looking for syllabus documents…
      </div>
    );
  }

  // Without a syllabus there is nothing to build from, so say what to do rather
  // than showing a control that cannot work.
  if (syllabi.length === 0) {
    return (
      <div className="p-8 text-center space-y-3">
        <Route className="w-8 h-8 text-on-surface-variant mx-auto" />
        <p className="text-sm text-on-surface">No syllabus to build from yet.</p>
        <p className="text-xs text-on-surface-variant max-w-md mx-auto leading-relaxed">
          Upload your syllabus in <strong className="text-on-surface">Library</strong> and tick
          “Mark uploaded files as Syllabus”. Once it finishes indexing it will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-5">
      <div className="space-y-1">
        <h3 className="font-editorial text-lg text-on-surface">
          {hasExistingRoadmap ? "Generate a new roadmap" : "Generate your roadmap"}
        </h3>
        <p className="text-xs text-on-surface-variant leading-relaxed">
          Atlas reads the syllabus and lays its topics out as a dependency graph.
        </p>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="syllabus-doc" className="block text-xs text-on-surface-variant font-semibold">
          Syllabus
        </label>
        <select
          id="syllabus-doc"
          value={documentId}
          onChange={(e) => setDocumentId(e.target.value)}
          disabled={generating}
          className="w-full min-h-[44px] px-3 bg-surface-container/50 border border-glass-border text-on-surface text-sm focus:outline-hidden focus:border-primary disabled:opacity-50"
        >
          {syllabi.map((d) => (
            <option key={d.id} value={d.id}>
              {d.filename}
            </option>
          ))}
        </select>
      </div>

      <fieldset className="space-y-1.5" disabled={generating}>
        <legend className="text-xs text-on-surface-variant font-semibold mb-1.5">Ordering</legend>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => setMode(m.id)}
              aria-pressed={mode === m.id}
              className={`p-3 border text-left transition disabled:opacity-50 ${
                mode === m.id
                  ? "bg-surface-container/70 border-primary"
                  : "border-glass-border hover:border-on-surface-variant"
              }`}
            >
              <div className="text-sm text-on-surface">{m.label}</div>
              <div className="text-[11px] text-on-surface-variant leading-snug mt-0.5">{m.blurb}</div>
            </button>
          ))}
        </div>
      </fieldset>

      {/* Generating replaces whatever is active, and the progress on it stops
          being visible. Better said before the click than discovered after. */}
      {hasExistingRoadmap && (
        <p className="text-[11px] text-luminous-highlight bg-primary-container/25 border border-primary/30 p-3 leading-relaxed">
          This archives your current roadmap. Its progress is kept, but it will no longer be the
          one shown here.
        </p>
      )}

      {error && (
        <p className="text-[11px] text-primary bg-primary-container/25 border border-primary/30 p-3 leading-relaxed">
          {error}
        </p>
      )}

      <button
        type="button"
        onClick={handleGenerate}
        disabled={generating || !documentId}
        className="w-full min-h-[44px] px-4 bg-primary text-white text-sm font-semibold flex items-center justify-center gap-2 hover:brightness-110 transition disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {generating ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Reading the syllabus…
          </>
        ) : (
          <>
            <Sparkles className="w-4 h-4" />
            Generate roadmap
          </>
        )}
      </button>

      {generating && (
        <p className="text-[11px] text-on-surface-variant text-center">
          This calls your chat model and can take up to a minute on a long syllabus.
        </p>
      )}
    </div>
  );
}
