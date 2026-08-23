import React, { useEffect, useState } from "react";
import { useProfileStore } from "../stores/profileStore";
import { analyticsApi, AnalyticsOverview, MasteryDistribution, WeaknessConcept } from "../api/analytics";
import { roadmapApi, RoadmapDetail } from "../api/roadmap";
import { Link, useNavigate } from "react-router-dom";
import {
  Brain,
  CheckCircle2,
  Clock,
  Flame,
  Layers,
  Sparkles,
  ArrowRight,
  AlertTriangle,
  BookOpen,
  Route,
  MessageSquare,
  Award,
} from "lucide-react";
import { CardSkeleton, Skeleton, EmptyState, ErrorState } from "../components/common/LoadingStates";

export function DashboardPage() {
  const navigate = useNavigate();
  const { activeProfileId, profiles } = useProfileStore();
  const activeProfile = profiles.find((p) => p.id === activeProfileId);

  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [activeRoadmap, setActiveRoadmap] = useState<RoadmapDetail | null>(null);
  const [mastery, setMastery] = useState<MasteryDistribution | null>(null);
  const [weaknesses, setWeaknesses] = useState<WeaknessConcept[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = () => {
    if (!activeProfileId) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    Promise.all([
      analyticsApi.getOverview(activeProfileId),
      roadmapApi.getActiveRoadmap(activeProfileId).catch((err) => {
        if (err?.response?.status === 404) return null;
        throw err;
      }),
      analyticsApi.getMastery(activeProfileId),
      analyticsApi.getWeaknesses(activeProfileId),
    ]).then(([nextOverview, nextRoadmap, nextMastery, nextWeaknesses]) => {
      setOverview(nextOverview);
      setActiveRoadmap(nextRoadmap);
      setMastery(nextMastery);
      setWeaknesses(nextWeaknesses);
    }).catch((err) => {
      setError(err?.response?.data?.error?.message || "Failed to load dashboard data.");
    }).finally(() => setLoading(false));
  };

  useEffect(() => { loadDashboard(); }, [activeProfileId]);

  if (!activeProfile) {
    return (
      <div className="p-8 max-w-xl mx-auto text-center py-20">
        <EmptyState
          icon={Brain}
          title="Welcome to Atlas"
          description="Create or select a learner profile to initialize your personalized workstation."
          actionLabel="Create Profile"
          onAction={() => navigate("/setup")}
        />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="w-full min-w-0 space-y-6">
        <Skeleton className="h-32 w-full rounded-2xl" />
        <CardSkeleton count={4} />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Skeleton className="h-64 rounded-2xl lg:col-span-2" />
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      </div>
    );
  }

  if (error) {
    return <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto"><ErrorState message={error} onRetry={loadDashboard} /></div>;
  }

  const completionPct = overview?.completion_percentage ?? 0;
  const avgMasteryPct = Math.round((overview?.average_mastery ?? 0) * 100);

  return (
    <div className="w-full min-w-0 space-y-6">
      {/* Welcome Editorial Glass Banner */}
      <div className="glass-panel p-6 sm:p-8 rounded-2xl border border-glass-border shadow-[0_4px_30px_rgba(0,0,0,0.1)] flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-primary-container/30 text-primary border border-glass-border uppercase tracking-widest">
              Active Polymath Flow
            </span>
          </div>
          <h1 className="font-editorial text-3xl sm:text-4xl text-on-surface mt-2 tracking-tight">
            Welcome back, {activeProfile.name}
          </h1>
          <p className="text-xs sm:text-sm text-on-surface-variant mt-1.5 font-sans">
            Target Track:{" "}
            <span className="font-semibold text-primary">
              {activeProfile.profile_type || "General"}
            </span>{" "}
            • 5-Pillar Context Active
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Link
            to="/chat"
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary hover:opacity-90 active:scale-95 text-on-primary text-xs font-semibold rounded-lg shadow-[0_0_15px_rgba(var(--accent-rgb),0.3)] transition"
          >
            <MessageSquare className="w-4 h-4" /> Start AI Tutor
          </Link>
          <Link
            to="/roadmap"
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-surface-container/60 hover:bg-surface-container-high/80 active:scale-95 text-on-surface text-xs font-semibold rounded-lg border border-glass-border transition"
          >
            <Route className="w-4 h-4" /> View Roadmap DAG
          </Link>
        </div>
      </div>

      {/* 4 Primary KPI Metric Cards (Frosted Glass Slabs) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Completion */}
        <div className="glass-card p-5 border border-glass-border flex flex-col justify-between hover:border-primary/40 transition duration-300">
          <div className="flex justify-between items-center mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-on-surface-variant">
              Syllabus Completion
            </span>
            <CheckCircle2 className="w-4 h-4 text-on-surface-variant" />
          </div>
          <div className="font-editorial text-3xl sm:text-4xl text-on-surface">
            {completionPct}%
          </div>
          <div className="w-full bg-surface-container-highest/50 rounded-full h-1.5 mt-3 overflow-hidden">
            <div
              className="bg-primary h-1.5 rounded-full transition-all duration-700 shadow-[0_0_8px_rgba(var(--accent-rgb),0.4)]"
              style={{ width: `${completionPct}%` }}
            />
          </div>
          <span className="text-[11px] text-on-surface-variant mt-2 font-sans">
            {overview?.completed_topics ?? 0} of {overview?.total_topics ?? 0} topics completed
          </span>
        </div>

        {/* Metric 2: Study Time */}
        <div className="glass-card p-5 border border-glass-border flex flex-col justify-between hover:border-primary/40 transition duration-300">
          <div className="flex justify-between items-center mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-primary">
              Total Study Time
            </span>
            <Clock className="w-4 h-4 text-primary" />
          </div>
          <div className="font-editorial text-3xl sm:text-4xl text-on-surface">
            {overview?.total_study_minutes ?? 0}{" "}
            <span className="text-sm font-sans text-on-surface-variant">mins</span>
          </div>
          <div className="text-[11px] text-on-surface-variant mt-2 font-sans">
            Across {overview?.total_sessions ?? 0} focused sessions
          </div>
        </div>

        {/* Metric 3: Average Mastery */}
        <div className="glass-card p-5 border border-glass-border flex flex-col justify-between hover:border-primary/40 transition duration-300">
          <div className="flex justify-between items-center mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-on-surface-variant">
              Average Mastery
            </span>
            <Award className="w-4 h-4 text-on-surface-variant" />
          </div>
          <div className="font-editorial text-3xl sm:text-4xl text-on-surface">
            {avgMasteryPct}%
          </div>
          <div className="w-full bg-surface-container-highest/50 rounded-full h-1.5 mt-3 overflow-hidden">
            <div
              className="bg-primary h-1.5 rounded-full transition-all duration-700 shadow-[0_0_8px_rgba(var(--accent-rgb),0.4)]"
              style={{ width: `${avgMasteryPct}%` }}
            />
          </div>
          <span className="text-[11px] text-on-surface-variant mt-2 font-sans">
            Concept retention & diagnostic rating
          </span>
        </div>

        {/* Metric 4: Daily Streak */}
        <div className="glass-card p-5 border border-glass-border flex flex-col justify-between hover:border-primary/40 transition duration-300">
          <div className="flex justify-between items-center mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-rose-400">
              Learning Velocity
            </span>
            <Flame className="w-4 h-4 text-rose-400" />
          </div>
          <div className="font-editorial text-3xl sm:text-4xl text-on-surface">
            {overview?.active_streak_days ?? 1}{" "}
            <span className="text-sm font-sans text-on-surface-variant">day streak</span>
          </div>
          <span className="text-[11px] text-on-surface-variant mt-2 font-sans">
            Keep your daily momentum alive
          </span>
        </div>
      </div>

      {/* Main Grid: Active Roadmap & Weakness Identification */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Active Roadmap & Current Node */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl border border-glass-border space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="font-editorial text-2xl text-on-surface">
                Active Roadmap
              </h2>
              <p className="text-xs text-on-surface-variant font-sans">
                {activeRoadmap?.title || "No active curriculum configured"}
              </p>
            </div>
            <Link
              to="/roadmap"
              className="text-xs text-primary hover:underline font-semibold flex items-center gap-1"
            >
              Interactive DAG <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          {activeRoadmap && activeRoadmap.nodes.length > 0 ? (
            <div className="space-y-3">
              {activeRoadmap.nodes.slice(0, 5).map((node, i) => (
                <div
                  key={node.id}
                  className="flex items-center justify-between p-3.5 rounded-xl bg-surface-container/30 border border-glass-border hover:bg-surface-container/60 transition"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded-md bg-surface-container-high/80 border border-glass-border flex items-center justify-center text-xs font-mono text-on-surface-variant">
                      {i + 1}
                    </div>
                    <div>
                      <h3 className="text-xs font-semibold text-on-surface">{node.title}</h3>
                      <p className="text-[10px] text-on-surface-variant capitalize">
                        {node.node_type} • Status: {node.status.replace("_", " ")}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono text-primary">
                      {Math.round(node.mastery_score * 100)}%
                    </span>
                    <Link
                      to={`/chat?topic=${encodeURIComponent(node.title)}`}
                      className="px-2.5 py-1 rounded bg-primary-container/40 hover:bg-primary-container/70 text-primary text-[11px] font-semibold border border-glass-border transition"
                    >
                      Study
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-6 text-center text-xs text-on-surface-variant">
              No topics in active roadmap. Upload a syllabus or generate a roadmap.
            </div>
          )}
        </div>

        {/* Target Focus Areas & Weaknesses */}
        <div className="glass-panel p-6 rounded-2xl border border-glass-border space-y-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-luminous-highlight" />
            <h2 className="font-editorial text-2xl text-on-surface">Focus Targets</h2>
          </div>
          <p className="text-xs text-on-surface-variant font-sans">
            AI detected concept areas needing revision:
          </p>

          {weaknesses.length > 0 ? (
            <div className="space-y-2.5">
              {weaknesses.slice(0, 4).map((w, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-primary-container/25 border border-primary/30 flex items-center justify-between"
                >
                  <div>
                    <h3 className="text-xs font-semibold text-on-surface">{w.title}</h3>
                    <p className="text-[10px] text-luminous-highlight">
                      Score: {Math.round((w.mastery_score ?? 0.4) * 100)}%
                    </p>
                  </div>
                  <Link
                    to={`/quiz?topic=${encodeURIComponent(w.title)}`}
                    className="text-[10px] font-semibold px-2 py-1 bg-primary/20 hover:bg-primary/30 text-luminous-highlight rounded border border-primary/30 transition"
                  >
                    Quiz
                  </Link>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-6 text-center text-xs text-on-surface-variant">
              No identified weak spots! Great work on topic mastery.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
