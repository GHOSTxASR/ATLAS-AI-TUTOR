import React, { useEffect, useState, useCallback } from "react";
import { useProfileStore } from "../stores/profileStore";
import {
  analyticsApi,
  AnalyticsOverview,
  ActivityHeatmapItem,
  MasteryDistribution,
  LearningVelocityPoint,
  WeaknessConcept,
} from "../api/analytics";
import {
  Brain,
  Calendar,
  CheckCircle2,
  Clock,
  Flame,
  Sparkles,
  AlertTriangle,
  Award,
  } from "lucide-react";
import { EmptyState, ErrorState } from "../components/common/LoadingStates";

export function AnalyticsPage() {
  const { activeProfileId, profiles } = useProfileStore();
  const activeProfile = profiles.find((p) => p.id === activeProfileId);

  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [heatmap, setHeatmap] = useState<ActivityHeatmapItem[]>([]);
  const [mastery, setMastery] = useState<MasteryDistribution | null>(null);
  const [, setVelocity] = useState<LearningVelocityPoint[]>([]);
  const [weaknesses, setWeaknesses] = useState<WeaknessConcept[]>([]);
  const [selectedMasteryTab, setSelectedMasteryTab] = useState<"mastered" | "proficient" | "needs_practice" | "unstarted">("needs_practice");
  const [, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadAnalytics = useCallback(() => {
    if (!activeProfileId) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    Promise.allSettled([
      analyticsApi.getOverview(activeProfileId),
      analyticsApi.getHeatmap(activeProfileId, 30),
      analyticsApi.getMastery(activeProfileId),
      analyticsApi.getVelocity(activeProfileId, 14),
      analyticsApi.getWeaknesses(activeProfileId),
    ]).then(([resOverview, resHeatmap, resMastery, resVelocity, resWeaknesses]) => {
      if (resOverview.status === "fulfilled") setOverview(resOverview.value);
      if (resHeatmap.status === "fulfilled") setHeatmap(resHeatmap.value);
      if (resMastery.status === "fulfilled") setMastery(resMastery.value);
      if (resVelocity.status === "fulfilled") setVelocity(resVelocity.value);
      if (resWeaknesses.status === "fulfilled") setWeaknesses(resWeaknesses.value);
      const failures = [resOverview, resHeatmap, resMastery, resVelocity, resWeaknesses].filter((result) => result.status === "rejected");
      if (failures.length > 0) setError("Some analytics data could not be loaded.");
      setLoading(false);
    });
  }, [activeProfileId]);

  useEffect(() => {
    loadAnalytics();
  }, [loadAnalytics]);

  if (!activeProfile) {
    return (
      <div className="p-8 text-center py-20">
        <EmptyState
          icon={Brain}
          title="No Active Profile"
          description="Please select or create a learner profile to view detailed learning analytics."
        />
      </div>
    );
  }

  if (error && !overview && !mastery) {
    return <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto"><ErrorState message={error} onRetry={loadAnalytics} /></div>;
  }

  const completionPct = overview?.completion_percentage ?? 0;
  const avgMasteryPct = Math.round((overview?.average_mastery ?? 0) * 100);

  const getActiveTopics = () => {
    if (!mastery) return [];
    if (selectedMasteryTab === "mastered") return mastery.mastered_topics || [];
    if (selectedMasteryTab === "proficient") return mastery.proficient_topics || [];
    if (selectedMasteryTab === "needs_practice") return mastery.needs_practice_topics || [];
    return mastery.unstarted_topics || [];
  };

  return (
    <div className="w-full min-w-0 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="atlas-label">
              Telemetry & Velocity
            </span>
          </div>
          <h1 className="font-editorial text-3xl sm:text-4xl text-on-surface mt-1.5 tracking-tight">
            Learning Analytics
          </h1>
          <p className="text-xs sm:text-sm text-on-surface-variant mt-1 font-sans">
            Study time metrics, syllabus progress, retention mastery, and concept telemetry for {activeProfile.name}.
          </p>
        </div>
        <div className="flex items-center gap-2 bg-primary-container/25 border border-primary/30 px-3.5 py-1.5 text-luminous-highlight text-xs font-semibold shadow-sm">
          <Flame className="w-4 h-4 text-luminous-highlight animate-pulse" />
          <span>{overview?.active_streak_days ?? 1} Day Streak</span>
        </div>
      </div>

      {error && (
        <ErrorState
          title="Some analytics are unavailable"
          message={error}
          onRetry={loadAnalytics}
        />
      )}

      {/* 4 Summary Metric Cards */}
      <div className="atlas-grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        {/* 1. Total Study Time */}
        <div className="glass-card p-5 border border-glass-border space-y-2">
          <div className="flex justify-between items-center text-on-surface-variant">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-primary">
              Total Study Time
            </span>
            <Clock className="w-4 h-4 text-primary" />
          </div>
          <div className="font-editorial text-3xl sm:text-4xl text-on-surface">
            {overview?.total_study_minutes ?? 0}{" "}
            <span className="text-sm font-sans text-on-surface-variant">mins</span>
          </div>
          <p className="text-[11px] text-on-surface-variant font-sans">Across dialogues & drills</p>
        </div>

        {/* 2. Syllabus Completion */}
        <div className="glass-card p-5 border border-glass-border space-y-2">
          <div className="flex justify-between items-center text-on-surface-variant">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-on-surface-variant">
              Syllabus Completion
            </span>
            <CheckCircle2 className="w-4 h-4 text-on-surface-variant" />
          </div>
          <div className="font-editorial text-3xl sm:text-4xl text-on-surface">
            {completionPct}%
          </div>
          <div className="w-full bg-surface-container-highest/50 h-1.5 overflow-hidden">
            <div
              className="bg-primary h-1.5"
              style={{ width: `${completionPct}%` }}
            />
          </div>
        </div>

        {/* 3. Average Mastery */}
        <div className="glass-card p-5 border border-glass-border space-y-2">
          <div className="flex justify-between items-center text-on-surface-variant">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-luminous-highlight">
              Average Mastery
            </span>
            <Award className="w-4 h-4 text-luminous-highlight" />
          </div>
          <div className="font-editorial text-3xl sm:text-4xl text-on-surface">
            {avgMasteryPct}%
          </div>
          <p className="text-[11px] text-on-surface-variant font-sans">Adaptive rating across nodes</p>
        </div>

        {/* 4. Quizzes Completed */}
        <div className="glass-card p-5 border border-glass-border space-y-2">
          <div className="flex justify-between items-center text-on-surface-variant">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-secondary">
              Quizzes Completed
            </span>
            <Sparkles className="w-4 h-4 text-secondary" />
          </div>
          <div className="font-editorial text-3xl sm:text-4xl text-on-surface">
            {overview?.total_quizzes_taken ?? 0}
          </div>
          <p className="text-[11px] text-on-surface-variant font-sans">Diagnostic attempts</p>
        </div>
      </div>

      {/* Activity Heatmap Grid */}
      <div className="glass-panel p-6 border border-glass-border space-y-4 shadow-[0_4px_30px_rgba(0,0,0,0.1)]">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="font-editorial text-2xl text-on-surface">30-Day Activity Heatmap</h2>
            <p className="text-xs text-on-surface-variant font-sans">
              Daily minutes spent studying, reading notes, and practicing quizzes.
            </p>
          </div>
          <Calendar className="w-5 h-5 text-on-surface-variant" />
        </div>

        <div className="grid grid-cols-6 sm:grid-cols-10 md:grid-cols-15 gap-2 pt-2">
          {heatmap.map((item, idx) => {
            const intensity =
              item.minutes === 0
                ? "bg-surface-container/40"
                : item.minutes < 15
                ? "bg-primary/30"
                : item.minutes < 45
                ? "bg-primary/60"
                : "bg-primary shadow-[0_0_8px_rgba(var(--accent-rgb),0.3)]";
            return (
              <div
                key={idx}
                title={`${item.date}: ${item.minutes} mins (${item.events_count} events)`}
                className={`h-7 border border-glass-border flex items-center justify-center text-[10px] font-mono transition-transform hover:scale-110 cursor-pointer ${intensity}`}
              >
                {item.minutes > 0 ? item.minutes : ""}
              </div>
            );
          })}
        </div>
      </div>

      {/* Mastery Breakdown & Weakness Focus */}
      <div className="atlas-grid grid-cols-1 lg:grid-cols-3">
        {/* Mastery Distribution */}
        <div className="lg:col-span-2 glass-panel p-6 border border-glass-border space-y-4">
          <h2 className="font-editorial text-2xl text-on-surface">Mastery Distribution</h2>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {([
              { id: "mastered", label: "Mastered (>85%)", count: mastery?.mastered_count ?? 0, color: "text-emerald-400" },
              { id: "proficient", label: "Proficient (60-85%)", count: mastery?.proficient_count ?? 0, color: "text-primary" },
              { id: "needs_practice", label: "Needs Practice (<60%)", count: mastery?.needs_practice_count ?? 0, color: "text-luminous-highlight" },
              { id: "unstarted", label: "Unstarted", count: mastery?.unstarted_count ?? 0, color: "text-on-surface-variant" },
            ] as const).map((tab) => (
              <button
                key={tab.id}
                onClick={() => setSelectedMasteryTab(tab.id)}
                className={`p-3 border text-left transition ${
                  selectedMasteryTab === tab.id
                    ? "bg-surface-container/70 border-primary shadow-[0_0_8px_rgba(var(--accent-rgb),0.2)] luminous-active"
                    : "bg-surface-container/30 border-glass-border hover:bg-surface-container/50"
                }`}
              >
                <div className={`font-editorial text-2xl ${tab.color}`}>{tab.count}</div>
                <div className="text-[11px] text-on-surface-variant font-sans mt-0.5">{tab.label}</div>
              </button>
            ))}
          </div>

          {/* List of Concepts in Selected Tab */}
          <div className="space-y-2 pt-2 max-h-60 overflow-y-auto">
            {getActiveTopics().map((c, i) => (
              <div
                key={i}
                className="p-3 bg-surface-container/30 border border-glass-border flex justify-between items-center text-xs"
              >
                <span className="font-semibold text-on-surface">{c.title}</span>
                <span className="font-mono text-primary">
                  {Math.round(c.mastery_score * 100)}%
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Weakness Concepts */}
        <div className="glass-panel p-6 border border-glass-border space-y-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-luminous-highlight" />
            <h2 className="font-editorial text-2xl text-on-surface">Review Focus</h2>
          </div>
          <p className="text-xs text-on-surface-variant font-sans">
            Concepts flagged for reinforcement based on diagnostic scoring:
          </p>

          <div className="space-y-2.5 max-h-80 overflow-y-auto">
            {weaknesses.map((w, idx) => (
              <div
                key={idx}
                className="p-3 bg-primary-container/25 border border-primary/30 flex items-center justify-between"
              >
                <div>
                  <h4 className="text-xs font-semibold text-on-surface">{w.title}</h4>
                  <span className="text-[10px] text-luminous-highlight font-mono">
                    Score: {Math.round((w.mastery_score ?? 0.4) * 100)}%
                  </span>
                </div>
              </div>
            ))}

            {weaknesses.length === 0 && (
              <div className="p-8 text-center text-xs text-on-surface-variant font-sans">
                No weak concepts flagged.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
