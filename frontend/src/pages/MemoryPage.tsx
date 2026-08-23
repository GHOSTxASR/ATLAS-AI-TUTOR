import React, { useEffect, useRef, useState } from "react";
import { useProfileStore } from "../stores/profileStore";
import { memoryApi, MemoryRecord, MemoryCategory } from "../api/memory";
import {
  Brain,
  Plus,
  Search,
  Trash2,
  Sparkles,
  AlertTriangle,
  Award,
  Target,
  HelpCircle,
  Bookmark,
  CheckCircle2,
  X,
} from "lucide-react";
import { CardSkeleton, EmptyState, ErrorState } from "../components/common/LoadingStates";
import { useFocusTrap } from "../hooks/useFocusTrap";

export function MemoryPage() {
  const { activeProfileId, profiles } = useProfileStore();
  const activeProfile = profiles.find((p) => p.id === activeProfileId);
  const modalRef = useRef<HTMLDivElement>(null);

  const [memories, setMemories] = useState<MemoryRecord[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);

  // Creation modal state
  const [showModal, setShowModal] = useState<boolean>(false);
  useFocusTrap(showModal, modalRef, () => setShowModal(false));
  const [subject, setSubject] = useState<string>("");
  const [content, setContent] = useState<string>("");
  const [category, setCategory] = useState<MemoryCategory>("weakness");
  const [confidence, setConfidence] = useState<number>(0.8);
  const [creating, setCreating] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadMemories = () => {
    if (!activeProfileId) return;
    setLoading(true);
    memoryApi
      .listMemories(activeProfileId, {
        category: selectedCategory === "all" ? undefined : selectedCategory,
      })
      .then((data) => setMemories(data))
      .catch((err) => console.error("Failed loading memories:", err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadMemories();
  }, [activeProfileId, selectedCategory]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProfileId || !subject.trim() || !content.trim()) return;

    setCreating(true);
    setActionError(null);
    try {
      await memoryApi.createMemory(activeProfileId, {
        subject: subject.trim(),
        content: content.trim(),
        category,
        confidence,
      });
      setShowModal(false);
      setSubject("");
      setContent("");
      loadMemories();
    } catch (err: any) {
      setActionError(err?.response?.data?.error?.message || "Failed to create memory.");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (memoryId: string) => {
    if (!activeProfileId) return;
    if (!window.confirm("Delete this memory record?")) return;
    try {
      await memoryApi.deleteMemory(activeProfileId, memoryId);
      loadMemories();
    } catch (err: any) {
      setActionError(err?.response?.data?.error?.message || "Failed to delete memory.");
    }
  };

  if (!activeProfile) {
    return (
      <div className="p-8 text-center py-20">
        <EmptyState
          icon={Brain}
          title="No Active Profile"
          description="Please select or create a learner profile to inspect and manage learner memory records."
        />
      </div>
    );
  }

  const categoryConfig: Record<
    MemoryCategory,
    { label: string; icon: any; color: string; bg: string }
  > = {
    weakness: {
      label: "Weaknesses",
      icon: AlertTriangle,
      color: "text-rose-400",
      bg: "bg-rose-500/10 border-rose-500/20",
    },
    strength: {
      label: "Strengths",
      icon: Award,
      color: "text-emerald-400",
      bg: "bg-emerald-500/10 border-emerald-500/20",
    },
    preference: {
      label: "Preferences",
      icon: Target,
      color: "text-primary",
      bg: "bg-primary-container/30 border-primary/30",
    },
    goal: {
      label: "Milestones",
      icon: Bookmark,
      color: "text-amber-300",
      bg: "bg-amber-500/10 border-amber-500/20",
    },
    fact: {
      label: "Facts",
      icon: CheckCircle2,
      color: "text-cyan-300",
      bg: "bg-cyan-500/10 border-cyan-500/20",
    },
    misconception: {
      label: "Misconceptions",
      icon: AlertTriangle,
      color: "text-rose-400",
      bg: "bg-rose-500/10 border-rose-500/20",
    },
  };

  const filteredMemories = memories.filter((m) => {
    const q = searchQuery.toLowerCase();
    return m.subject.toLowerCase().includes(q) || m.content.toLowerCase().includes(q);
  });

  return (
    <div className="w-full min-w-0 space-y-6">
      {actionError && <ErrorState message={actionError} actionLabel="Dismiss" onRetry={() => setActionError(null)} />}
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-primary-container/30 text-primary border border-glass-border uppercase tracking-widest">
              Long-Term Cognitive Store
            </span>
          </div>
          <h1 className="font-editorial text-3xl sm:text-4xl text-on-surface mt-1.5 tracking-tight">
            Memory Vault
          </h1>
          <p className="text-xs sm:text-sm text-on-surface-variant mt-1 font-sans">
            AI extracted learner profiles, strengths, misconceptions, and learning preferences with time-decay.
          </p>
        </div>

        <button
          onClick={() => setShowModal(true)}
          className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-primary hover:opacity-90 active:scale-95 text-on-primary text-xs font-semibold rounded-lg shadow-[0_0_12px_rgba(var(--accent-rgb),0.25)] transition"
        >
          <Plus className="w-4 h-4" /> Add Memory Record
        </button>
      </div>

      {/* Filter Tabs & Search */}
      <div className="glass-panel p-3.5 rounded-2xl border border-glass-border flex flex-col sm:flex-row justify-between items-center gap-3">
        <div className="flex gap-1.5 overflow-x-auto min-w-0 w-full sm:w-auto">
          {[
            { id: "all", label: "All Records" },
            { id: "weakness", label: "Weaknesses" },
            { id: "strength", label: "Strengths" },
            { id: "preference", label: "Preferences" },
            { id: "goal", label: "Milestones" },
            { id: "fact", label: "Facts" },
          ].map((cat) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition ${
                selectedCategory === cat.id
                  ? "bg-primary text-on-primary shadow-[0_0_8px_rgba(var(--accent-rgb),0.3)]"
                  : "bg-surface-container/40 text-on-surface-variant hover:text-on-surface border border-glass-border"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        <div className="w-full sm:w-72 sm:shrink-0">
          <input
            type="text"
            placeholder="Search memory vault..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-3.5 py-1.5 bg-surface-container/50 border border-glass-border rounded-lg text-xs text-on-surface placeholder:text-on-surface-variant/60 focus:outline-hidden focus:border-primary transition"
          />
        </div>
      </div>

      {/* Memory Cards Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <CardSkeleton count={6} />
        </div>
      ) : filteredMemories.length === 0 ? (
        <div className="glass-panel p-12 text-center rounded-2xl border border-glass-border text-xs text-on-surface-variant font-sans">
          No cognitive memory records match this query.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredMemories.map((m) => {
            const conf = categoryConfig[m.category] || categoryConfig.fact;
            const Icon = conf.icon;
            return (
              <div
                key={m.id}
                className="glass-card p-5 border border-glass-border flex flex-col justify-between space-y-3 hover:border-primary/40 transition duration-300"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className={`p-1.5 rounded-md ${conf.bg} ${conf.color}`}>
                        <Icon className="w-3.5 h-3.5" />
                      </span>
                      <span className="text-[10px] font-mono uppercase font-semibold text-on-surface-variant">
                        {conf.label}
                      </span>
                    </div>

                    <button
                      onClick={() => handleDelete(m.id)}
                      className="p-1 rounded text-on-surface-variant hover:text-rose-400 hover:bg-rose-500/10 transition"
                      title="Delete record"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <h3 className="font-semibold text-xs sm:text-sm text-on-surface mt-2.5">
                    {m.subject}
                  </h3>
                  <p className="text-xs text-on-surface-variant mt-1 font-sans leading-relaxed">
                    {m.content}
                  </p>
                </div>

                <div className="pt-2 border-t border-glass-border flex items-center justify-between text-[10px] font-mono text-on-surface-variant">
                  <span>Confidence: {Math.round(m.confidence * 100)}%</span>
                  <span className="capitalize">Active: {m.is_active ? "Yes" : "Archived"}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add Memory Modal */}
      {showModal && (
        <div ref={modalRef} className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="new-memory-title">
          <form
            onSubmit={handleCreate}
            className="glass-panel w-full max-w-md p-6 rounded-2xl border border-glass-border space-y-4 shadow-2xl"
          >
            <div className="flex justify-between items-center">
              <h3 id="new-memory-title" className="font-editorial text-xl text-on-surface">New Cognitive Memory</h3>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                aria-label="Close new memory dialog"
                className="p-1 rounded-md text-on-surface-variant hover:bg-surface-bright/20"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 font-sans text-xs">
              <div>
                <label className="block text-on-surface-variant mb-1 font-semibold">Subject / Concept</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Eigenvalues, Integration by Parts"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden focus:border-primary"
                />
              </div>

              <div>
                <label className="block text-on-surface-variant mb-1 font-semibold">Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value as MemoryCategory)}
                  className="w-full px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden"
                >
                  <option value="weakness" className="bg-surface text-on-surface">Weakness / Misconception</option>
                  <option value="strength" className="bg-surface text-on-surface">Strength / Mastery</option>
                  <option value="preference" className="bg-surface text-on-surface">Learning Preference</option>
                  <option value="goal" className="bg-surface text-on-surface">Milestone Goal</option>
                  <option value="fact" className="bg-surface text-on-surface">Learner Fact</option>
                </select>
              </div>

              <div>
                <label className="block text-on-surface-variant mb-1 font-semibold">Observation Detail</label>
                <textarea
                  rows={3}
                  required
                  placeholder="e.g. Struggles with boundary conditions in definite integrals..."
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden focus:border-primary"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="px-4 py-2 rounded-lg text-xs text-on-surface-variant hover:text-on-surface"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={creating}
                className="px-4 py-2 bg-primary hover:opacity-90 disabled:opacity-40 text-on-primary text-xs font-semibold rounded-lg shadow-sm"
              >
                {creating ? "Storing..." : "Store Memory"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
