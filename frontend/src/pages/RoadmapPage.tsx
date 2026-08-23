import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useProfileStore } from "../stores/profileStore";
import {
  roadmapApi,
  RoadmapDetail,
  RoadmapNode,
  RoadmapProgress,
} from "../api/roadmap";
import {
  Route,
  CheckCircle2,
  Clock,
  Sparkles,
  Layers,
  ArrowRight,
  Brain,
  MessageSquare,
  Award,
  Lock,
  Unlock,
  ChevronRight,
  AlertCircle,
} from "lucide-react";
import { CardSkeleton, Skeleton, EmptyState, ErrorState } from "../components/common/LoadingStates";

export function RoadmapPage() {
  const { activeProfileId, profiles } = useProfileStore();
  const activeProfile = profiles.find((p) => p.id === activeProfileId);
  const [searchParams] = useSearchParams();
  const urlNodeId = searchParams.get("node_id");

  const [roadmap, setRoadmap] = useState<RoadmapDetail | null>(null);
  const [selectedNode, setSelectedNode] = useState<RoadmapNode | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [modeFilter, setModeFilter] = useState<string>("all");
  const [actionError, setActionError] = useState<string | null>(null);

  // The topic actually being studied: whatever is in progress, else the first
  // unfinished one. Used to give the header action a real destination.
  const currentNode =
    roadmap?.nodes?.find((n) => n.status === "in_progress") ??
    roadmap?.nodes?.find((n) => n.status !== "completed" && n.status !== "skipped") ??
    null;

  const loadRoadmap = () => {
    if (!activeProfileId) return;
    setLoading(true);
    roadmapApi
      .getActiveRoadmap(activeProfileId)
      .then((data) => {
        setRoadmap(data);
        if (data.nodes && data.nodes.length > 0) {
          if (urlNodeId) {
            const matched = data.nodes.find((n) => n.id === urlNodeId);
            if (matched) {
              setSelectedNode(matched);
              return;
            }
          }
          if (!selectedNode) {
            setSelectedNode(data.nodes[0]);
          }
        }
      })
      .catch((err) => {
        if (err?.response?.status === 404) {
          setRoadmap(null);
          setSelectedNode(null);
          return;
        }
        console.error("Failed to load active roadmap:", err);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadRoadmap();
  }, [activeProfileId, urlNodeId]);

  const handleUpdateStatus = async (
    nodeId: string,
    status: "not_started" | "in_progress" | "completed" | "skipped" | "flagged"
  ) => {
    if (!activeProfileId || !roadmap) return;
    setActionError(null);
    try {
      await roadmapApi.updateNodeStatus(activeProfileId, roadmap.id, nodeId, { status });
      loadRoadmap();
    } catch (err: any) {
      setActionError(err?.response?.data?.error?.message || "Failed updating roadmap status.");
    }
  };

  if (!activeProfile) {
    return (
      <div className="p-8 text-center py-20">
        <EmptyState
          icon={Route}
          title="No Active Profile"
          description="Please select or create a learner profile to inspect and generate study roadmaps."
        />
      </div>
    );
  }

  const completionPct = roadmap?.progress?.completion_percentage ?? 0;
  const avgMastery = Math.round((roadmap?.progress?.average_mastery ?? 0) * 100);

  return (
    <div className="w-full min-w-0 space-y-6">
      {actionError && <ErrorState message={actionError} actionLabel="Dismiss" onRetry={() => setActionError(null)} />}
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="atlas-label">
              Topological DAG
            </span>
            {roadmap?.mode && (
              <span className="px-2.5 py-0.5 text-[10px] font-mono uppercase bg-surface-container-high text-primary border border-glass-border">
                {roadmap.mode} Mode
              </span>
            )}
          </div>
          <h1 className="font-editorial text-3xl sm:text-4xl text-on-surface mt-1.5 tracking-tight">
            Curriculum Roadmap
          </h1>
          <p className="text-xs sm:text-sm text-on-surface-variant mt-1 font-sans">
            Dynamic dependency graph sequencing concepts from foundational prerequisites to advanced mastery.
          </p>
        </div>

        {/* Named the "current node" but linked to a bare /chat, carrying no
            topic at all. It now opens the tutor on the topic actually in
            progress, and names it so the destination is predictable. */}
        {currentNode && (
          <div className="flex items-center gap-3 shrink-0">
            <Link
              to={`/chat?topic=${encodeURIComponent(currentNode.title)}`}
              title={`Open the AI tutor on "${currentNode.title}"`}
              className="atlas-btn atlas-btn-primary max-w-[16rem]"
            >
              <MessageSquare className="w-4 h-4 shrink-0" />
              <span className="truncate">Study {currentNode.title}</span>
            </Link>
          </div>
        )}
      </div>

      {/* Progress & Health Cards */}
      <div className="atlas-grid grid-cols-1 sm:grid-cols-3">
        <div className="glass-card p-5 border border-glass-border flex flex-col justify-between">
          <div className="flex justify-between items-center mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-on-surface-variant">
              Curriculum Progress
            </span>
            <CheckCircle2 className="w-4 h-4 text-on-surface-variant" />
          </div>
          <div className="font-editorial text-3xl sm:text-4xl text-on-surface">
            {completionPct}%
          </div>
          <div className="w-full bg-surface-container-highest/50 h-1.5 mt-3 overflow-hidden">
            <div
              className="bg-primary h-1.5 transition-all duration-500 shadow-[0_0_8px_rgba(var(--accent-rgb),0.4)]"
              style={{ width: `${completionPct}%` }}
            />
          </div>
        </div>

        <div className="glass-card p-5 border border-glass-border flex flex-col justify-between">
          <div className="flex justify-between items-center mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-primary">
              Average Mastery Score
            </span>
            <Award className="w-4 h-4 text-primary" />
          </div>
          <div className="font-editorial text-3xl sm:text-4xl text-on-surface">
            {avgMastery}%
          </div>
          <div className="w-full bg-surface-container-highest/50 h-1.5 mt-3 overflow-hidden">
            <div
              className="bg-primary h-1.5 transition-all duration-500 shadow-[0_0_8px_rgba(var(--accent-rgb),0.4)]"
              style={{ width: `${avgMastery}%` }}
            />
          </div>
        </div>

        <div className="glass-card p-5 border border-glass-border flex flex-col justify-between">
          <div className="flex justify-between items-center mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-secondary">
              Total DAG Vertices
            </span>
            <Layers className="w-4 h-4 text-secondary" />
          </div>
          <div className="font-editorial text-3xl sm:text-4xl text-on-surface">
            {roadmap?.nodes?.length ?? 0}{" "}
            <span className="text-sm font-sans text-on-surface-variant">topics</span>
          </div>
          <span className="text-[11px] text-on-surface-variant mt-2 font-sans">
            {roadmap?.progress?.in_progress_nodes ?? 0} in progress
          </span>
        </div>
      </div>

      {/* Main Grid: Sequential Node List & Detail Panel */}
      <div className="atlas-grid grid-cols-1 lg:grid-cols-3">
        {/* Nodes List */}
        <div className="lg:col-span-2 glass-panel p-6 border border-glass-border space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="font-editorial text-2xl text-on-surface">
              {roadmap?.title || "Sequenced Curriculum Topics"}
            </h2>
            <div className="text-xs text-on-surface-variant font-mono">
              Version {roadmap?.version || 1}
            </div>
          </div>

          {roadmap && roadmap.nodes && roadmap.nodes.length > 0 ? (
            <div className="space-y-3">
              {roadmap.nodes.map((node, index) => {
                const isSelected = selectedNode?.id === node.id;
                return (
                  <div
                    key={node.id}
                    onClick={() => setSelectedNode(node)}
                    className={`p-4 border transition-all cursor-pointer flex items-center justify-between gap-4 ${
                      isSelected
                        ? "bg-surface-container/70 border-primary shadow-[0_0_12px_rgba(var(--accent-rgb),0.15)] luminous-active"
                        : "bg-surface-container/30 hover:bg-surface-container/60 border-glass-border"
                    }`}
                  >
                    <div className="flex items-center gap-3.5 min-w-0">
                      <div
                        className={`w-7 h-7 flex items-center justify-center text-xs font-mono shrink-0 border border-glass-border ${
                          node.status === "completed"
                            ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                            : node.status === "in_progress"
                            ? "bg-primary-container/40 text-primary border-primary/30"
                            : "bg-surface-container-high text-on-surface-variant"
                        }`}
                      >
                        {node.status === "completed" ? (
                          <CheckCircle2 className="w-4 h-4" />
                        ) : (
                          index + 1
                        )}
                      </div>

                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold text-xs sm:text-sm text-on-surface truncate">
                            {node.title}
                          </h3>
                          {node.ai_generated && (
                            <Sparkles className="w-3 h-3 text-luminous-highlight shrink-0" />
                          )}
                        </div>
                        <p className="text-[11px] text-on-surface-variant mt-0.5 truncate font-sans capitalize">
                          {node.node_type} • Status: {node.status.replace("_", " ")}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <span className="text-xs font-mono text-primary">
                        {Math.round(node.mastery_score * 100)}%
                      </span>
                      <ChevronRight className="w-4 h-4 text-on-surface-variant" />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-8 text-center text-xs text-on-surface-variant font-sans">
              No topics found in active roadmap. Upload a syllabus or generate a curriculum.
            </div>
          )}
        </div>

        {/* Selected Node Details & Status Management */}
        <div className="glass-panel p-6 border border-glass-border space-y-5">
          {selectedNode ? (
            <>
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-primary-container/40 text-primary uppercase">
                    {selectedNode.node_type}
                  </span>
                  <span className="text-xs font-mono text-on-surface-variant">
                    Order #{selectedNode.order_index}
                  </span>
                </div>
                <h3 className="font-editorial text-2xl text-on-surface mt-2">
                  {selectedNode.title}
                </h3>
                <p className="text-xs text-on-surface-variant mt-1.5 font-sans leading-relaxed">
                  {selectedNode.description || "No topic description provided."}
                </p>
              </div>

              {/* Status Update Buttons */}
              <div className="space-y-2 pt-2 border-t border-glass-border">
                <label className="text-xs font-semibold text-on-surface block">
                  Update Learning State
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => handleUpdateStatus(selectedNode.id, "in_progress")}
                    className="atlas-btn"
                  >
                    In Progress
                  </button>
                  <button
                    onClick={() => handleUpdateStatus(selectedNode.id, "completed")}
                    className="px-3 py-2 bg-emerald-500/20 hover:bg-emerald-500/30 text-xs font-semibold text-emerald-300 border border-emerald-500/30 transition"
                  >
                    Mark Done
                  </button>
                  <button
                    onClick={() => handleUpdateStatus(selectedNode.id, "skipped")}
                    className="atlas-btn"
                  >
                    Skip
                  </button>
                  <button
                    onClick={() => handleUpdateStatus(selectedNode.id, "flagged")}
                    className="px-3 py-2 bg-primary/20 hover:bg-primary/30 text-xs font-semibold text-luminous-highlight border border-primary/30 transition"
                  >
                    Needs Review
                  </button>
                </div>
              </div>

              {/* Actions */}
              <div className="pt-3 border-t border-glass-border space-y-2">
                <Link
                  to={`/chat?topic=${encodeURIComponent(selectedNode.title)}`}
                  className="atlas-btn atlas-btn-primary w-full"
                >
                  <MessageSquare className="w-4 h-4" /> Start AI Tutorial
                </Link>
                <Link
                  to={`/quiz?topic=${encodeURIComponent(selectedNode.title)}`}
                  className="atlas-btn w-full"
                >
                  <Award className="w-4 h-4 text-luminous-highlight" /> Take Diagnostic Quiz
                </Link>
              </div>
            </>
          ) : (
            <div className="p-8 text-center text-xs text-on-surface-variant font-sans">
              Select a node from the roadmap to inspect details and actions.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
