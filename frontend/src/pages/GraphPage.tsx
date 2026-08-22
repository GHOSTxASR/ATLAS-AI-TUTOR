import React, { useEffect, useRef, useState } from "react";
import { useProfileStore } from "../stores/profileStore";
import {
  graphApi,
  GraphDataResponse,
  GraphNode,
  GraphEdge,
  GraphNodeType,
  GraphEdgeType,
} from "../api/graph";
import { KnowledgeGraphCanvas } from "../components/graph/KnowledgeGraphCanvas";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  Network,
  Plus,
  Link as LinkIcon,
  Sparkles,
  Search,
  Compass,
  MessageSquare,
  Award,
  Trash2,
  X,
} from "lucide-react";
import { CardSkeleton, EmptyState, ErrorState } from "../components/common/LoadingStates";
import { useFocusTrap } from "../hooks/useFocusTrap";

export function GraphPage() {
  const navigate = useNavigate();
  const { activeProfileId, profiles } = useProfileStore();
  const activeProfile = profiles.find((p) => p.id === activeProfileId);
  const [searchParams] = useSearchParams();
  const urlNodeId = searchParams.get("node_id");

  const [graphData, setGraphData] = useState<GraphDataResponse | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedType, setSelectedType] = useState<string>("all");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Pathfinding State
  const [pathSourceId, setPathSourceId] = useState<string>("");
  const [pathTargetId, setPathTargetId] = useState<string>("");
  const [highlightPathIds, setHighlightPathIds] = useState<string[]>([]);
  const [pathInfo, setPathInfo] = useState<string | null>(null);

  // Modals
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [newLabel, setNewLabel] = useState<string>("");
  const [newType, setNewType] = useState<GraphNodeType>("concept");
  const [newDesc, setNewDesc] = useState<string>("");
  const [newMastery, setNewMastery] = useState<number>(0.0);

  const [showLinkModal, setShowLinkModal] = useState<boolean>(false);
  const [linkSource, setLinkSource] = useState<string>("");
  const [linkTarget, setLinkTarget] = useState<string>("");
  const [linkType, setLinkType] = useState<GraphEdgeType>("prerequisite_of");

  const [showEnrichModal, setShowEnrichModal] = useState<boolean>(false);
  const modalRef = useRef<HTMLDivElement>(null);
  useFocusTrap(showAddModal || showLinkModal || showEnrichModal, modalRef, () => {
    setShowAddModal(false);
    setShowLinkModal(false);
    setShowEnrichModal(false);
  });
  const [enrichText, setEnrichText] = useState<string>("");
  const [enrichSourceLabel, setEnrichSourceLabel] = useState<string>("");

  const loadGraph = () => {
    if (!activeProfileId) return;
    setLoading(true);
    setError(null);
    graphApi
      .getGraph(activeProfileId)
      .then((data) => {
        setGraphData(data);
        if (data.nodes.length > 0) {
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
      .catch((err) => setError(err?.response?.data?.error?.message || "Failed to load knowledge graph."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadGraph();
  }, [activeProfileId, urlNodeId]);

  const handleCreateNode = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProfileId || !newLabel.trim()) return;
    setActionError(null);

    try {
      const node = await graphApi.createNode(activeProfileId, {
        label: newLabel.trim(),
        type: newType,
        description: newDesc.trim() || undefined,
        mastery_score: newMastery,
      });
      setShowAddModal(false);
      setNewLabel("");
      setNewDesc("");
      setNewMastery(0.0);
      loadGraph();
      setSelectedNode(node);
    } catch (err: any) {
      setActionError(err?.response?.data?.error?.message || "Failed to create node.");
    }
  };

  const handleCreateEdge = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProfileId || !linkSource || !linkTarget) return;
    setActionError(null);

    try {
      await graphApi.createEdge(activeProfileId, {
        source: linkSource,
        target: linkTarget,
        type: linkType,
      });
      setShowLinkModal(false);
      loadGraph();
    } catch (err: any) {
      setActionError(err?.response?.data?.error?.message || "Failed to link concepts.");
    }
  };

  const handleEnrichGraph = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProfileId || !enrichText.trim()) return;
    setActionError(null);
    setLoading(true);
    try {
      const updated = await graphApi.enrichGraph(activeProfileId, {
        text: enrichText.trim(),
        source_label: enrichSourceLabel.trim() || undefined,
      });
      setGraphData(updated);
      setShowEnrichModal(false);
      setEnrichText("");
      setEnrichSourceLabel("");
    } catch (err: any) {
      setActionError(err?.response?.data?.error?.message || "Failed to enrich graph.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteNode = async (nodeId: string) => {
    if (!activeProfileId || !confirm("Remove this concept from Knowledge Graph?")) return;
    try {
      await graphApi.deleteNode(activeProfileId, nodeId);
      if (selectedNode?.id === nodeId) setSelectedNode(null);
      loadGraph();
    } catch (err: any) {
      setActionError(err?.response?.data?.error?.message || "Failed to delete node.");
    }
  };

  const handleUpdateMastery = async (score: number) => {
    if (!activeProfileId || !selectedNode) return;
    try {
      const updated = await graphApi.updateNode(activeProfileId, selectedNode.id, {
        mastery_score: score,
      });
      setSelectedNode(updated);
      loadGraph();
    } catch (err: any) {
      setActionError(err?.response?.data?.error?.message || "Failed to update mastery.");
    }
  };

  const handleFindPath = async () => {
    if (!activeProfileId || !pathSourceId || !pathTargetId) return;
    try {
      const res = await graphApi.findPath(activeProfileId, pathSourceId, pathTargetId);
      if (res.path && res.path.length > 0) {
        setHighlightPathIds(res.path.map((n) => n.id));
        setPathInfo(`Found ${res.length}-hop shortest prerequisite route`);
      } else {
        setHighlightPathIds([]);
        setPathInfo("No directed path found between these concepts");
      }
    } catch (err: any) {
      setHighlightPathIds([]);
      setPathInfo("Path search error: " + (err?.message || "Not reachable"));
    }
  };

  const handleClearPath = () => {
    setPathSourceId("");
    setPathTargetId("");
    setHighlightPathIds([]);
    setPathInfo(null);
  };

  if (!activeProfile) {
    return (
      <div className="p-8 max-w-xl mx-auto text-center py-20">
        <EmptyState
          icon={Network}
          title="Select a Learner Profile"
          description="Create or select a profile to explore your interactive concept graph."
          actionLabel="Go to Setup"
          onAction={() => navigate("/setup")}
        />
      </div>
    );
  }

  if (error && !graphData) {
    return <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto"><ErrorState message={error} onRetry={loadGraph} /></div>;
  }

  const nodes = graphData?.nodes || [];
  const links = graphData?.links || [];

  const filteredNodes = nodes.filter((n) => {
    const matchesSearch =
      n.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (n.description && n.description.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesType = selectedType === "all" || n.type === selectedType;
    return matchesSearch && matchesType;
  });

  return (
    <div className="w-full min-w-0 space-y-6">
      {actionError && <ErrorState message={actionError} actionLabel="Dismiss" onRetry={() => setActionError(null)} />}
      {/* Header & Main Actions */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-primary-container/30 text-primary border border-glass-border uppercase tracking-widest">
              Neural Concept Atlas
            </span>
          </div>
          <h1 className="font-editorial text-3xl sm:text-4xl text-on-surface mt-1.5 tracking-tight">
            Knowledge Graph
          </h1>
          <p className="text-xs sm:text-sm text-on-surface-variant mt-1 font-sans">
            Semantic concept topology, prerequisite routing, and mastery nodes for {activeProfile.name}.
          </p>
        </div>
        <div className="flex flex-wrap gap-2.5">
          <button
            onClick={() => setShowEnrichModal(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-primary hover:opacity-90 active:scale-95 text-on-primary text-xs font-semibold rounded-lg shadow-[0_0_12px_rgba(160,240,237,0.25)] transition"
          >
            <Sparkles className="w-3.5 h-3.5" /> AI Extract
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-surface-container/60 hover:bg-surface-container-high/80 active:scale-95 text-on-surface text-xs font-semibold rounded-lg border border-glass-border transition"
          >
            <Plus className="w-3.5 h-3.5" /> Add Concept
          </button>
          {/* Linking needs two concepts to join. The button used to open a
              modal whose dropdowns had nothing to pick, which read as broken. */}
          <button
            onClick={() => setShowLinkModal(true)}
            disabled={nodes.length < 2}
            title={
              nodes.length < 2
                ? "Add at least two concepts before linking them"
                : "Create a relationship between two concepts"
            }
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-surface-container/60 hover:bg-surface-container-high/80 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100 text-on-surface text-xs font-semibold rounded-lg border border-glass-border transition"
          >
            <LinkIcon className="w-3.5 h-3.5" /> Link
          </button>
        </div>
      </div>

      {/* 4 KPI Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="glass-card p-4 border border-glass-border">
          <div className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider">
            Total Concepts
          </div>
          <div className="font-editorial text-2xl sm:text-3xl text-primary mt-1">
            {graphData?.stats?.concepts_count ?? 0}
          </div>
        </div>
        <div className="glass-card p-4 border border-glass-border">
          <div className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider">
            Prerequisites & Links
          </div>
          <div className="font-editorial text-2xl sm:text-3xl text-emerald-400 mt-1">
            {graphData?.stats?.total_edges ?? 0}
          </div>
        </div>
        <div className="glass-card p-4 border border-glass-border">
          <div className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider">
            Average Mastery
          </div>
          <div className="font-editorial text-2xl sm:text-3xl text-amber-300 mt-1">
            {Math.round((graphData?.stats?.average_mastery ?? 0) * 100)}%
          </div>
        </div>
        <div className="glass-card p-4 border border-glass-border">
          <div className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider">
            Source Documents
          </div>
          <div className="font-editorial text-2xl sm:text-3xl text-secondary mt-1">
            {graphData?.stats?.documents_count ?? 0}
          </div>
        </div>
      </div>

      {/* Main Interactive Canvas.
          An empty atlas used to render as a blank dark rectangle with no
          indication of what to do next. */}
      <div className="relative glass-panel p-2 rounded-2xl border border-glass-border shadow-[0_4px_30px_rgba(0,0,0,0.1)]">
        <KnowledgeGraphCanvas
          nodes={filteredNodes}
          edges={links}
          selectedNodeId={selectedNode?.id || null}
          highlightPathIds={highlightPathIds}
          onSelectNode={setSelectedNode}
        />
        {!loading && nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="max-w-xs text-center px-6">
              <Network className="w-8 h-8 mx-auto text-on-surface-variant/50" />
              <p className="mt-3 font-editorial text-lg text-on-surface">Your atlas is empty</p>
              <p className="mt-1 text-xs text-on-surface-variant leading-relaxed">
                Add a concept by hand, or use <span className="text-primary">AI Extract</span> to
                pull concepts out of your notes and documents.
              </p>
            </div>
          </div>
        )}
        {!loading && nodes.length > 0 && filteredNodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <p className="text-xs text-on-surface-variant">
              No concepts match this filter.
            </p>
          </div>
        )}
      </div>

      {/* Path Finder & Filter Toolbar */}
      <div className="glass-panel p-5 rounded-2xl border border-glass-border space-y-4">
        <div className="flex flex-col sm:flex-row gap-3 justify-between items-center">
          {/* Node Type Filters */}
          <div className="flex gap-1.5 overflow-x-auto min-w-0 w-full sm:w-auto">
            {["all", "concept", "chapter", "subject", "document"].map((t) => (
              <button
                key={t}
                onClick={() => setSelectedType(t)}
                className={`px-3 py-1 rounded-lg text-xs font-semibold capitalize transition ${
                  selectedType === t
                    ? "bg-primary text-on-primary shadow-[0_0_10px_rgba(160,240,237,0.3)]"
                    : "bg-surface-container/40 text-on-surface-variant hover:text-on-surface border border-glass-border"
                }`}
              >
                {t}s
              </button>
            ))}
          </div>

          {/* Search Box */}
          <div className="w-full sm:w-64 sm:shrink-0">
            <input
              type="text"
              placeholder="Search concepts on atlas..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-3 py-1.5 bg-surface-container/50 border border-glass-border rounded-lg text-xs text-on-surface placeholder:text-on-surface-variant/60 focus:outline-hidden focus:border-primary transition"
            />
          </div>
        </div>

        {/* Shortest Path Finder Bar */}
        <div className="pt-3 border-t border-glass-border flex flex-col sm:flex-row items-center gap-3">
          <span className="text-xs font-semibold text-on-surface whitespace-nowrap flex items-center gap-1">
            <Compass className="w-3.5 h-3.5 text-primary" /> Path Finder:
          </span>
          <select
            value={pathSourceId}
            onChange={(e) => setPathSourceId(e.target.value)}
            className="p-1.5 text-xs bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden"
          >
            <option value="">-- From Concept --</option>
            {nodes
              .filter((n) => n.type === "concept")
              .map((n) => (
                <option key={n.id} value={n.id} className="bg-surface text-on-surface">
                  {n.label}
                </option>
              ))}
          </select>
          <span className="text-xs text-on-surface-variant">→</span>
          <select
            value={pathTargetId}
            onChange={(e) => setPathTargetId(e.target.value)}
            className="p-1.5 text-xs bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden"
          >
            <option value="">-- To Concept --</option>
            {nodes
              .filter((n) => n.type === "concept" && n.id !== pathSourceId)
              .map((n) => (
                <option key={n.id} value={n.id} className="bg-surface text-on-surface">
                  {n.label}
                </option>
              ))}
          </select>
          <button
            onClick={handleFindPath}
            disabled={!pathSourceId || !pathTargetId}
            className="px-3.5 py-1.5 bg-primary hover:opacity-90 text-on-primary text-xs font-semibold rounded-lg shadow-sm transition disabled:opacity-40"
          >
            Find Route
          </button>
          {highlightPathIds.length > 0 && (
            <button
              onClick={handleClearPath}
              className="px-2.5 py-1.5 text-xs text-on-surface-variant hover:text-on-surface font-semibold"
            >
              Clear Route
            </button>
          )}
          {pathInfo && <span className="text-xs font-mono text-primary ml-auto">{pathInfo}</span>}
        </div>
      </div>

      {/* Selected Concept Detail Drawer */}
      {selectedNode && (
        <div className="glass-panel p-6 rounded-2xl border border-glass-border space-y-4 shadow-[0_4px_30px_rgba(0,0,0,0.1)]">
          <div className="flex justify-between items-start">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-primary-container/40 text-primary uppercase">
                  {selectedNode.type}
                </span>
                <h2 className="font-editorial text-2xl text-on-surface">{selectedNode.label}</h2>
              </div>
              <p className="text-xs text-on-surface-variant mt-1.5 font-sans">
                {selectedNode.description || "No detailed description recorded."}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Link
                to={`/chat?topic=${encodeURIComponent(selectedNode.label)}`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary hover:opacity-90 text-on-primary text-xs font-semibold transition"
              >
                <MessageSquare className="w-3.5 h-3.5" /> Tutor Topic
              </Link>
              <button
                onClick={() => handleDeleteNode(selectedNode.id)}
                className="p-1.5 rounded-lg text-on-surface-variant hover:bg-rose-500/20 hover:text-rose-400 transition"
                title="Delete Concept"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Mastery Rating Control */}
          <div className="flex items-center gap-3 pt-3 border-t border-glass-border">
            <span className="text-xs font-semibold text-on-surface">Concept Mastery:</span>
            <div className="flex gap-1.5">
              {[0, 0.25, 0.5, 0.75, 1.0].map((score) => (
                <button
                  key={score}
                  onClick={() => handleUpdateMastery(score)}
                  className={`px-2.5 py-1 rounded text-xs font-mono transition ${
                    selectedNode.mastery_score === score
                      ? "bg-primary text-on-primary font-bold shadow-[0_0_8px_rgba(160,240,237,0.3)]"
                      : "bg-surface-container/50 text-on-surface-variant hover:text-on-surface border border-glass-border"
                  }`}
                >
                  {Math.round(score * 100)}%
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Add Concept Modal */}
      {showAddModal && (
        <div ref={modalRef} className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="add-concept-title">
          <form
            onSubmit={handleCreateNode}
            className="glass-panel w-full max-w-md p-6 rounded-2xl border border-glass-border space-y-4 shadow-2xl"
          >
            <div className="flex justify-between items-center">
              <h3 id="add-concept-title" className="font-editorial text-xl text-on-surface">Add New Concept</h3>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                aria-label="Close add concept dialog"
                className="p-1 rounded-md text-on-surface-variant hover:bg-surface-bright/20"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 font-sans text-xs">
              <div>
                <label className="block text-on-surface-variant mb-1 font-semibold">Concept Label</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Fourier Transform"
                  value={newLabel}
                  onChange={(e) => setNewLabel(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden focus:border-primary"
                />
              </div>

              <div>
                <label className="block text-on-surface-variant mb-1 font-semibold">Type</label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value as GraphNodeType)}
                  className="w-full px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden"
                >
                  <option value="concept" className="bg-surface text-on-surface">Concept</option>
                  <option value="chapter" className="bg-surface text-on-surface">Chapter</option>
                  <option value="subject" className="bg-surface text-on-surface">Subject</option>
                </select>
              </div>

              <div>
                <label className="block text-on-surface-variant mb-1 font-semibold">Description</label>
                <textarea
                  rows={3}
                  placeholder="Summary or mathematical definition..."
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden focus:border-primary"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="px-4 py-2 rounded-lg text-xs text-on-surface-variant hover:text-on-surface"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-primary hover:opacity-90 text-on-primary text-xs font-semibold rounded-lg shadow-sm"
              >
                Create Concept
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Link Concepts Modal */}
      {showLinkModal && (
        <div ref={modalRef} className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="link-concepts-title">
          <form
            onSubmit={handleCreateEdge}
            className="glass-panel w-full max-w-md p-6 rounded-2xl border border-glass-border space-y-4 shadow-2xl"
          >
            <div className="flex justify-between items-center">
              <h3 id="link-concepts-title" className="font-editorial text-xl text-on-surface">Link Concepts</h3>
              <button
                type="button"
                onClick={() => setShowLinkModal(false)}
                aria-label="Close link concepts dialog"
                className="p-1 rounded-md text-on-surface-variant hover:bg-surface-bright/20"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 font-sans text-xs">
              <div>
                <label className="block text-on-surface-variant mb-1 font-semibold">Source Concept</label>
                <select
                  required
                  value={linkSource}
                  onChange={(e) => setLinkSource(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden"
                >
                  <option value="">-- Choose Source --</option>
                  {nodes.map((n) => (
                    <option key={n.id} value={n.id} className="bg-surface text-on-surface">
                      {n.label} ({n.type})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-on-surface-variant mb-1 font-semibold">Relationship</label>
                <select
                  value={linkType}
                  onChange={(e) => setLinkType(e.target.value as GraphEdgeType)}
                  className="w-full px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden"
                >
                  <option value="prerequisite_of" className="bg-surface text-on-surface">Prerequisite Of</option>
                  <option value="related_to" className="bg-surface text-on-surface">Related To</option>
                  <option value="taught_in" className="bg-surface text-on-surface">Taught In</option>
                  <option value="referenced_by" className="bg-surface text-on-surface">Referenced By</option>
                </select>
              </div>

              <div>
                <label className="block text-on-surface-variant mb-1 font-semibold">Target Concept</label>
                <select
                  required
                  value={linkTarget}
                  onChange={(e) => setLinkTarget(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden"
                >
                  <option value="">-- Choose Target --</option>
                  {nodes
                    .filter((n) => n.id !== linkSource)
                    .map((n) => (
                      <option key={n.id} value={n.id} className="bg-surface text-on-surface">
                        {n.label} ({n.type})
                      </option>
                    ))}
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowLinkModal(false)}
                className="px-4 py-2 rounded-lg text-xs text-on-surface-variant hover:text-on-surface"
              >
                Cancel
              </button>
              {/* Both ends must be chosen, and a concept cannot link to
                  itself, so the action stays disabled until it can succeed. */}
              <button
                type="submit"
                disabled={!linkSource || !linkTarget || linkSource === linkTarget}
                className="px-4 py-2 bg-primary hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed text-on-primary text-xs font-semibold rounded-lg shadow-sm transition"
              >
                Create Edge
              </button>
            </div>
          </form>
        </div>
      )}

      {/* AI Enrich Modal */}
      {showEnrichModal && (
        <div ref={modalRef} className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Enrich knowledge graph">
          <form
            onSubmit={handleEnrichGraph}
            className="glass-panel w-full max-w-lg p-6 rounded-2xl border border-glass-border space-y-4 shadow-2xl"
          >
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-primary" />
                <h3 className="font-editorial text-xl text-on-surface">AI Concept Extraction</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowEnrichModal(false)}
                className="p-1 rounded-md text-on-surface-variant hover:bg-surface-bright/20"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 font-sans text-xs">
              <div>
                <label className="block text-on-surface-variant mb-1 font-semibold">
                  Source Name / Reference (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Chapter 4 Notes, Lecture 2"
                  value={enrichSourceLabel}
                  onChange={(e) => setEnrichSourceLabel(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden focus:border-primary"
                />
              </div>

              <div>
                <label className="block text-on-surface-variant mb-1 font-semibold">Text or Syllabus Content</label>
                <textarea
                  rows={6}
                  required
                  placeholder="Paste lecture text, book excerpt, or syllabus concepts..."
                  value={enrichText}
                  onChange={(e) => setEnrichText(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden focus:border-primary"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowEnrichModal(false)}
                className="px-4 py-2 rounded-lg text-xs text-on-surface-variant hover:text-on-surface"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-primary hover:opacity-90 text-on-primary text-xs font-semibold rounded-lg shadow-[0_0_12px_rgba(160,240,237,0.3)]"
              >
                Extract & Map
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
