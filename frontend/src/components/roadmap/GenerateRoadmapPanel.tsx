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
  const [materials, setMaterials] = useState<Document[]>([]);
  const [documentId, setDocumentId] = useState("");
  const [source, setSource] = useState<"syllabus" | "materials">("syllabus");
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
        // Only what finished indexing has any text to read.
        const indexed = docs.filter((d) => d.status === "indexed");
        const marked = indexed.filter((d) => d.is_syllabus);
        setSyllabi(marked);
        setMaterials(indexed);
        setDocumentId((current) => current || marked[0]?.id || "");
        // Nobody marked a syllabus, but there is still a course in these
        // files: fall back to writing the curriculum out of them.
        setSource(marked.length > 0 ? "syllabus" : "materials");
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

  const usingMaterials = source === "materials";

  const handleGenerate = async () => {
    if (usingMaterials ? materials.length === 0 : !documentId) return;
    setGenerating(true);
    setError(null);
    try {
      await roadmapApi.generateRoadmap(
        profileId,
        usingMaterials
          ? { document_ids: materials.map((d) => d.id), mode }
          : {
              document_id: documentId,
              mode,
              title: syllabi
                .find((d) => d.id === documentId)
                ?.filename.replace(/\.[^.]+$/, ""),
            },
      );
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
        Looking through your library…
      </div>
    );
  }

  // A missing syllabus is no longer a dead end -- the materials can be read
  // instead -- so this is only for a library with nothing indexed in it.
  if (materials.length === 0) {
    return (
      <div className="p-8 text-center space-y-3">
        <Route className="w-8 h-8 text-on-surface-variant mx-auto" />
        <p className="text-sm text-on-surface">Nothing to build from yet.</p>
        <p className="text-xs text-on-surface-variant max-w-md mx-auto leading-relaxed">
          Upload your syllabus or your course materials in{" "}
          <strong className="text-on-surface">Library</strong>. Once they finish indexing they
          will appear here.
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
          {usingMaterials
            ? "No syllabus is marked, so Atlas reads your materials, works out the course they teach, and lays its topics out as a dependency graph."
            : "Atlas reads the syllabus and lays its topics out as a dependency graph."}
        </p>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="syllabus-doc" className="block text-xs text-on-surface-variant font-semibold">
          {usingMaterials ? "Build from" : "Syllabus"}
        </label>

        {usingMaterials ? (
          <div className="border border-glass-border bg-surface-container/50 p-3 space-y-2">
            <p className="text-xs text-on-surface leading-relaxed">
              Reading {materials.length} {materials.length === 1 ? "document" : "documents"} and
              writing the curriculum they teach, in the order it should be learned.
            </p>
            <ul className="text-[11px] text-on-surface-variant space-y-0.5 max-h-28 overflow-y-auto">
              {materials.map((d) => (
                <li key={d.id}>{d.filename}</li>
              ))}
            </ul>
          </div>
        ) : (
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
        )}

        {/* Only worth offering when there is actually a choice to make. */}
        {syllabi.length > 0 && (
          <button
            type="button"
            disabled={generating}
            onClick={() => setSource(usingMaterials ? "syllabus" : "materials")}
            className="text-[11px] text-primary hover:underline disabled:opacity-50"
          >
            {usingMaterials
              ? "Use one of my syllabus documents instead"
              : "No syllabus for this? Build one from all my materials"}
          </button>
        )}
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

      {/* What happens next depends on what was uploaded, and it is worth
          saying before the click rather than leaving it to be discovered. */}
      {hasExistingRoadmap && (
        <p className="text-[11px] text-luminous-highlight bg-primary-container/25 border border-primary/30 p-3 leading-relaxed">
          An updated syllabus for the same course folds into your current roadmap: topics you
          have already worked on keep their progress, and new ones are added alongside them. A
          syllabus for a different subject starts a separate roadmap instead, and this one is
          kept as history.
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
        disabled={generating || (usingMaterials ? materials.length === 0 : !documentId)}
        className="w-full min-h-[44px] px-4 bg-primary text-white text-sm font-semibold flex items-center justify-center gap-2 hover:brightness-110 transition disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {generating ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            {usingMaterials ? "Working out your curriculum…" : "Reading the syllabus…"}
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
          {usingMaterials
            ? "This reads every document you have and can take a couple of minutes. Leave it running."
            : "This calls your chat model and can take up to a minute on a long syllabus."}
        </p>
      )}
    </div>
  );
}
