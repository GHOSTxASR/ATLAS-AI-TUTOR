import React, { useEffect, useState } from "react";
import { useProfileStore } from "../stores/profileStore";
import { ProfileType } from "../types";
import {
  User,
  Plus,
  CheckCircle2,
  Trash2,
  Edit3,
  Sparkles,
  Layers,
  GraduationCap,
  ShieldCheck,
  Check,
} from "lucide-react";
import { CardSkeleton, Skeleton, EmptyState } from "../components/common/LoadingStates";

const PROFILE_TYPES: ProfileType[] = ["JEE", "GATE", "Semester Study", "Custom Learning"];

export function SetupPage() {
  const {
    profiles,
    activeProfileId,
    isLoading,
    error,
    loadProfiles,
    createProfile,
    updateProfile,
    deleteProfile,
    setActiveProfile,
  } = useProfileStore();

  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<ProfileType>("JEE");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");

  useEffect(() => {
    loadProfiles();
  }, [loadProfiles]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    await createProfile({ name: newName.trim(), profile_type: newType });
    setNewName("");
  };

  const handleStartEdit = (id: string, currentName: string) => {
    setEditingId(id);
    setEditName(currentName);
  };

  const handleSaveEdit = async (id: string) => {
    if (editName.trim()) {
      await updateProfile(id, { name: editName.trim() });
    }
    setEditingId(null);
  };

  return (
    <div className="w-full min-w-0 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-primary-container/30 text-primary border border-glass-border uppercase tracking-widest">
            Profile Isolation & Storage
          </span>
        </div>
        <h1 className="font-editorial text-3xl sm:text-4xl text-on-surface mt-1.5 tracking-tight">
          Learner Profiles
        </h1>
        <p className="text-xs sm:text-sm text-on-surface-variant mt-1 font-sans">
          Create and switch between distinct target curriculums, competitive exams, or college courses with partitioned vectors and memory.
        </p>
      </div>

      {error && (
        <div role="alert" className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-xs font-semibold">
          {error}
        </div>
      )}

      {/* Profile Creation Card */}
      <div className="glass-panel p-6 rounded-2xl border border-glass-border space-y-4 shadow-[0_4px_30px_rgba(0,0,0,0.1)]">
        <h2 className="font-editorial text-2xl text-on-surface flex items-center gap-2">
          <Plus className="w-5 h-5 text-primary" />
          Create New Learner Profile
        </h2>

        <form onSubmit={handleCreate} className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end font-sans text-xs">
          <div className="sm:col-span-2">
            <label className="block text-on-surface-variant mb-1 font-semibold">
              Profile / Learner Name *
            </label>
            <input
              type="text"
              required
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. Ashmit (JEE Prep 2026)"
              className="w-full px-3.5 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface placeholder:text-on-surface-variant/60 focus:outline-hidden focus:border-primary"
            />
          </div>

          <div>
            <label className="block text-on-surface-variant mb-1 font-semibold">
              Target Track
            </label>
            <select
              value={newType}
              onChange={(e) => setNewType(e.target.value as ProfileType)}
              className="w-full px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden focus:border-primary"
            >
              {PROFILE_TYPES.map((t) => (
                <option key={t} value={t} className="bg-surface text-on-surface">
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div className="sm:col-span-3 pt-1">
            <button
              type="submit"
              disabled={isLoading || !newName.trim()}
              className="w-full py-2.5 bg-primary hover:opacity-90 disabled:opacity-40 text-on-primary text-xs font-semibold rounded-xl shadow-[0_0_12px_rgba(var(--accent-rgb),0.25)] transition flex items-center justify-center gap-2"
            >
              <Sparkles className="w-4 h-4" /> Create Profile
            </button>
          </div>
        </form>
      </div>

      {/* Profiles List */}
      <section className="space-y-4">
        <h2 className="font-editorial text-2xl text-on-surface">Existing Profiles</h2>

        {isLoading ? (
          <CardSkeleton count={3} />
        ) : profiles.length === 0 ? (
          <div className="glass-panel p-10 text-center rounded-2xl border border-glass-border text-xs text-on-surface-variant font-sans">
            No learner profiles found. Create your first profile above to get started.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {profiles.map((p) => {
              const isActive = activeProfileId === p.id;
              return (
                <div
                  key={p.id}
                  className={`glass-card p-5 border transition-all duration-300 flex flex-col justify-between space-y-4 ${
                    isActive
                      ? "bg-surface-container/70 border-primary shadow-[0_0_15px_rgba(var(--accent-rgb),0.2)] luminous-active"
                      : "bg-surface-container/30 border-glass-border hover:border-primary/40"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      {editingId === p.id ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            className="px-2 py-1 bg-surface-container border border-primary rounded text-xs text-on-surface font-sans"
                            autoFocus
                          />
                          <button
                            onClick={() => handleSaveEdit(p.id)}
                            className="p-1 rounded bg-primary text-on-primary text-xs font-semibold"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ) : (
                        <h3 className="font-editorial text-2xl text-on-surface truncate">
                          {p.name}
                        </h3>
                      )}
                      <p className="text-xs text-primary font-mono mt-0.5">
                        {p.profile_type}
                      </p>
                    </div>

                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleStartEdit(p.id, p.name)}
                        className="p-1.5 rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-bright/20 transition"
                        title="Rename Profile"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => deleteProfile(p.id)}
                        className="p-1.5 rounded-lg text-on-surface-variant hover:text-rose-400 hover:bg-rose-500/20 transition"
                        title="Delete Profile"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  <div className="pt-3 border-t border-glass-border flex items-center justify-between">
                    {/* A truncated UUID is developer noise to a learner; the
                        creation date is something they can actually use to
                        tell two profiles apart. */}
                    <span className="text-[10px] text-on-surface-variant" title={p.id}>
                      Created{" "}
                      {new Date(p.created_at).toLocaleDateString(undefined, {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </span>

                    {isActive ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-400">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Active Workstation
                      </span>
                    ) : (
                      <button
                        onClick={() => setActiveProfile(p.id)}
                        className="px-3 py-1 bg-surface-container/60 hover:bg-surface-container-high text-xs font-semibold text-on-surface rounded-lg border border-glass-border transition"
                      >
                        Switch to Profile
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
