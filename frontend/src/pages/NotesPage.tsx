import React, { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useProfileStore } from "../stores/profileStore";
import { notesApi, NoteResponse, NoteSummary, NoteType } from "../api/notes";
import { roadmapApi, RoadmapNode } from "../api/roadmap";
import {
  BookOpen,
  Plus,
  Search,
  Zap,
  FileText,
  Table,
  Trash2,
  Edit3,
  Copy,
  Check,
  Sparkles,
  Layers,
  X,
} from "lucide-react";
import { MarkdownContent } from "../components/common/MarkdownContent";
import { CardSkeleton, Skeleton, EmptyState, ErrorState } from "../components/common/LoadingStates";
import { useFocusTrap } from "../hooks/useFocusTrap";

export function NotesPage() {
  const { activeProfileId, profiles } = useProfileStore();
  const activeProfile = profiles.find((p) => p.id === activeProfileId);
  const modalRef = useRef<HTMLDivElement>(null);
  const [searchParams] = useSearchParams();
  const urlNoteId = searchParams.get("note_id");

  const [notes, setNotes] = useState<NoteSummary[]>([]);
  const [selectedNote, setSelectedNote] = useState<NoteResponse | null>(null);
  const [selectedType, setSelectedType] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [copied, setCopied] = useState<boolean>(false);

  // Generation Modal
  const [showGenModal, setShowGenModal] = useState<boolean>(false);
  useFocusTrap(showGenModal, modalRef, () => setShowGenModal(false));
  const [genTopic, setGenTopic] = useState<string>("");
  const [genType, setGenType] = useState<NoteType>("lesson_note");
  const [genInstructions, setGenInstructions] = useState<string>("");
  const [generating, setGenerating] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Roadmap Nodes for dropdown
  const [roadmapNodes, setRoadmapNodes] = useState<RoadmapNode[]>([]);
  const [selectedRoadmapNodeId, setSelectedRoadmapNodeId] = useState<string>("");

  const loadNotes = () => {
    if (!activeProfileId) return;
    setLoading(true);
    notesApi
      .listNotes(activeProfileId, {
        note_type: selectedType === "all" ? undefined : selectedType,
        q: searchQuery.trim() || undefined,
      })
      .then((data) => {
        setNotes(data);
        if (data.length > 0) {
          if (urlNoteId) {
            const matched = data.find((n) => n.id === urlNoteId);
            if (matched) {
              loadSingleNote(matched.id);
              return;
            }
          }
          if (!selectedNote) {
            loadSingleNote(data[0].id);
          }
        } else {
          setSelectedNote(null);
        }
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  const loadSingleNote = (noteId: string) => {
    if (!activeProfileId) return;
    notesApi
      .getNote(activeProfileId, noteId)
      .then((data) => setSelectedNote(data))
      .catch((err) => console.error(err));
  };

  useEffect(() => {
    const timeout = window.setTimeout(loadNotes, 250);
    return () => window.clearTimeout(timeout);
  }, [activeProfileId, selectedType, searchQuery, urlNoteId]);

  useEffect(() => {
    if (activeProfileId) {
      roadmapApi
        .getActiveRoadmap(activeProfileId)
        .then((r) => setRoadmapNodes(r.nodes || []))
        .catch(() => setRoadmapNodes([]));
    }
  }, [activeProfileId]);

  const handleGenerateNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProfileId || !genTopic.trim()) return;

    setGenerating(true);
    setActionError(null);
    try {
      const created = await notesApi.generateNote(activeProfileId, {
        topic_title: genTopic.trim(),
        note_type: genType,
        roadmap_node_id: selectedRoadmapNodeId || undefined,
        custom_instructions: genInstructions.trim() || undefined,
      });
      setShowGenModal(false);
      setGenTopic("");
      setGenInstructions("");
      setSelectedRoadmapNodeId("");
      loadNotes();
      setSelectedNote(created);
    } catch (err: any) {
      setActionError(err?.response?.data?.error?.message || "Failed generating note.");
    } finally {
      setGenerating(false);
    }
  };

  const handleDeleteNote = async (noteId: string) => {
    if (!activeProfileId || !confirm("Delete this study note?")) return;
    try {
      await notesApi.deleteNote(activeProfileId, noteId);
      loadNotes();
      if (selectedNote?.id === noteId) setSelectedNote(null);
    } catch (err: any) {
      setActionError(err?.response?.data?.error?.message || "Failed to delete note.");
    }
  };

  const handleCopy = () => {
    if (!selectedNote) return;
    navigator.clipboard.writeText(selectedNote.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!activeProfile) {
    return (
      <div className="p-8 text-center py-20">
        <EmptyState
          icon={BookOpen}
          title="No Active Profile"
          description="Please select or create a learner profile to manage and generate study notes."
        />
      </div>
    );
  }

  const noteTypes = [
    { id: "all", label: "All Notes" },
    { id: "lesson_note", label: "Lesson Notes" },
    { id: "revision_note", label: "Revision Drills" },
    { id: "cheat_sheet", label: "Formula Sheets" },
    { id: "summary", label: "Summaries" },
  ];

  return (
    <div className="w-full min-w-0 space-y-6">
      {actionError && <ErrorState message={actionError} actionLabel="Dismiss" onRetry={() => setActionError(null)} />}
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-primary-container/30 text-primary border border-glass-border uppercase tracking-widest">
              Synthesized Knowledge
            </span>
          </div>
          <h1 className="font-editorial text-3xl sm:text-4xl text-on-surface mt-1.5 tracking-tight">
            Study Notes & Cheat Sheets
          </h1>
          <p className="text-xs sm:text-sm text-on-surface-variant mt-1 font-sans">
            AI-grounded multimodal note generation across lesson notes, high-yield revisions, and formula sheets.
          </p>
        </div>

        <button
          onClick={() => setShowGenModal(true)}
          className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-primary hover:opacity-90 active:scale-95 text-on-primary text-xs font-semibold rounded-lg shadow-[0_0_12px_rgba(160,240,237,0.25)] transition"
        >
          <Sparkles className="w-4 h-4" /> Generate AI Note
        </button>
      </div>

      {/* Filter Tabs & Search Bar */}
      <div className="glass-panel p-3.5 rounded-2xl border border-glass-border flex flex-col sm:flex-row justify-between items-center gap-3 min-w-0">
        <div className="flex gap-1.5 overflow-x-auto min-w-0 w-full sm:w-auto">
          {noteTypes.map((t) => (
            <button
              key={t.id}
              onClick={() => setSelectedType(t.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition ${
                selectedType === t.id
                  ? "bg-primary text-on-primary shadow-[0_0_8px_rgba(160,240,237,0.3)]"
                  : "bg-surface-container/40 text-on-surface-variant hover:text-on-surface border border-glass-border"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="w-full sm:w-72 sm:shrink-0">
          <input
            type="text"
            placeholder="Search notes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-3.5 py-1.5 bg-surface-container/50 border border-glass-border rounded-lg text-xs text-on-surface placeholder:text-on-surface-variant/60 focus:outline-hidden focus:border-primary transition"
          />
        </div>
      </div>

      {/* Main Grid: Notes List + Selected Note Reader */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Notes List Column */}
        <div className="glass-panel p-4 rounded-2xl border border-glass-border space-y-2 max-h-[calc(100vh-18rem)] overflow-y-auto">
          {loading ? (
            <CardSkeleton count={4} />
          ) : notes.length === 0 ? (
            <div className="p-8 text-center text-xs text-on-surface-variant font-sans">
              No notes found. Click "Generate AI Note" to create one.
            </div>
          ) : (
            notes.map((note) => {
              const isSelected = selectedNote?.id === note.id;
              return (
                <div
                  key={note.id}
                  onClick={() => loadSingleNote(note.id)}
                  className={`p-3.5 rounded-xl border transition-all cursor-pointer flex flex-col gap-1.5 ${
                    isSelected
                      ? "bg-surface-container/70 border-primary shadow-[0_0_10px_rgba(160,240,237,0.15)] luminous-active"
                      : "bg-surface-container/30 hover:bg-surface-container/60 border-glass-border"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-container-high text-primary uppercase">
                      {note.note_type.replace("_", " ")}
                    </span>
                    <span className="text-[10px] text-on-surface-variant font-mono">
                      {new Date(note.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <h3 className="font-semibold text-xs sm:text-sm text-on-surface truncate">
                    {note.title}
                  </h3>
                </div>
              );
            })
          )}
        </div>

        {/* Note Reader Viewport */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl border border-glass-border space-y-4 max-h-[calc(100vh-18rem)] overflow-y-auto">
          {selectedNote ? (
            <>
              <div className="flex justify-between items-start pb-3 border-b border-glass-border">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-primary-container/40 text-primary uppercase">
                      {selectedNote.note_type.replace("_", " ")}
                    </span>
                    <span className="text-xs text-on-surface-variant font-mono">
                      Source: {selectedNote.source}
                    </span>
                  </div>
                  <h2 className="font-editorial text-2xl sm:text-3xl text-on-surface mt-2">
                    {selectedNote.title}
                  </h2>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleCopy}
                    aria-label={copied ? "Copied markdown" : "Copy markdown"}
                    className="p-2 rounded-lg bg-surface-container/50 hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface border border-glass-border transition"
                    title="Copy Markdown"
                  >
                    {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  </button>
                  <button
                    onClick={() => handleDeleteNote(selectedNote.id)}
                    aria-label="Delete note"
                    className="p-2 rounded-lg hover:bg-rose-500/20 text-on-surface-variant hover:text-rose-400 border border-transparent hover:border-rose-500/30 transition"
                    title="Delete Note"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Note Markdown Content */}
              <div className="text-xs sm:text-sm leading-relaxed text-on-surface">
                <MarkdownContent content={selectedNote.content} />
              </div>
            </>
          ) : (
            <div className="p-12 text-center text-xs text-on-surface-variant font-sans">
              Select a note from the left to read its contents.
            </div>
          )}
        </div>
      </div>

      {/* AI Generate Modal */}
      {showGenModal && (
        <div ref={modalRef} className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="generate-note-title">
          <form
            onSubmit={handleGenerateNote}
            className="glass-panel w-full max-w-lg p-6 rounded-2xl border border-glass-border space-y-4 shadow-2xl"
          >
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-primary" />
                <h3 id="generate-note-title" className="font-editorial text-xl text-on-surface">Generate AI Study Note</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowGenModal(false)}
                aria-label="Close generate note dialog"
                className="p-1 rounded-md text-on-surface-variant hover:bg-surface-bright/20"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 font-sans text-xs">
              <div>
                <label className="block text-on-surface-variant mb-1 font-semibold">Concept or Topic</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Thermodynamics Carnot Cycle"
                  value={genTopic}
                  onChange={(e) => setGenTopic(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden focus:border-primary"
                />
              </div>

              <div>
                <label className="block text-on-surface-variant mb-1 font-semibold">Modality / Note Type</label>
                <select
                  value={genType}
                  onChange={(e) => setGenType(e.target.value as NoteType)}
                  className="w-full px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden"
                >
                  <option value="lesson_note" className="bg-surface text-on-surface">Lesson Note (Deep Explanations)</option>
                  <option value="revision_note" className="bg-surface text-on-surface">Revision Note (High Yield Bullet Points)</option>
                  <option value="cheat_sheet" className="bg-surface text-on-surface">Cheat Sheet (Key Formulas & Rules)</option>
                  <option value="summary" className="bg-surface text-on-surface">Summary (Executive Overview)</option>
                </select>
              </div>

              {roadmapNodes.length > 0 && (
                <div>
                  <label className="block text-on-surface-variant mb-1 font-semibold">Link to Roadmap Node (Optional)</label>
                  <select
                    value={selectedRoadmapNodeId}
                    onChange={(e) => setSelectedRoadmapNodeId(e.target.value)}
                    className="w-full px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden"
                  >
                    <option value="">-- None --</option>
                    {roadmapNodes.map((n) => (
                      <option key={n.id} value={n.id} className="bg-surface text-on-surface">
                        {n.title}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label className="block text-on-surface-variant mb-1 font-semibold">Custom Instructions (Optional)</label>
                <textarea
                  rows={3}
                  placeholder="e.g. Focus on edge case derivations, include ASCII diagram..."
                  value={genInstructions}
                  onChange={(e) => setGenInstructions(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden focus:border-primary"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowGenModal(false)}
                className="px-4 py-2 rounded-lg text-xs text-on-surface-variant hover:text-on-surface"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={generating}
                className="px-4 py-2 bg-primary hover:opacity-90 disabled:opacity-40 text-on-primary text-xs font-semibold rounded-lg shadow-[0_0_12px_rgba(160,240,237,0.3)]"
              >
                {generating ? "Synthesizing..." : "Generate Note"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
