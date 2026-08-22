import React, { useEffect, useRef, useState, useMemo, useCallback } from "react";
import { GraphNode, GraphEdge } from "../../api/graph";

interface Point {
  x: number;
  y: number;
}

interface SimulatedNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
}

interface KnowledgeGraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId: string | null;
  highlightPathIds?: string[];
  onSelectNode: (node: GraphNode | null) => void;
}

export function KnowledgeGraphCanvas({
  nodes,
  edges,
  selectedNodeId,
  highlightPathIds = [],
  onSelectNode,
}: KnowledgeGraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [transform, setTransform] = useState<{ x: number; y: number; k: number }>({
    x: 400,
    y: 300,
    k: 1.0,
  });
  const [isPanning, setIsPanning] = useState(false);
  const [startPan, setStartPan] = useState<Point>({ x: 0, y: 0 });
  const [draggedNodeId, setDraggedNodeId] = useState<string | null>(null);

  // Simulated node positions
  const [simNodes, setSimNodes] = useState<SimulatedNode[]>([]);

  // Initialize simulation positions in a ring/circle layout
  useEffect(() => {
    if (nodes.length === 0) {
      setSimNodes([]);
      return;
    }

    const radiusBase = Math.min(300, Math.max(120, nodes.length * 20));
    const initialized: SimulatedNode[] = nodes.map((node, i) => {
      // Check if existing position exists
      const existing = simNodes.find((sn) => sn.id === node.id);
      if (existing) {
        return {
          ...existing,
          ...node,
          radius: Math.min(36, Math.max(18, 16 + (node.mention_count || 1) * 2)),
        };
      }
      const angle = (i / nodes.length) * 2 * Math.PI;
      return {
        ...node,
        x: Math.cos(angle) * radiusBase + (Math.random() - 0.5) * 40,
        y: Math.sin(angle) * radiusBase + (Math.random() - 0.5) * 40,
        vx: 0,
        vy: 0,
        radius: Math.min(36, Math.max(18, 16 + (node.mention_count || 1) * 2)),
      };
    });

    setSimNodes(initialized);
  }, [nodes]);

  // Run force-directed physics iteration
  useEffect(() => {
    if (simNodes.length === 0) return;

    let animId: number;
    let iteration = 0;
    const maxIterations = 80;

    const tick = () => {
      setSimNodes((currentNodes) => {
        if (currentNodes.length === 0) return currentNodes;
        const next = currentNodes.map((n) => ({ ...n }));
        const kRepulse = 1800;
        const kAttract = 0.04;
        const damping = 0.85;

        // 1. Repulsion between all node pairs
        for (let i = 0; i < next.length; i++) {
          for (let j = i + 1; j < next.length; j++) {
            const dx = next[i].x - next[j].x;
            const dy = next[i].y - next[j].y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            if (dist < 400) {
              const force = kRepulse / (dist * dist);
              const fx = (dx / dist) * force;
              const fy = (dy / dist) * force;
              if (next[i].id !== draggedNodeId) {
                next[i].vx += fx;
                next[i].vy += fy;
              }
              if (next[j].id !== draggedNodeId) {
                next[j].vx -= fx;
                next[j].vy -= fy;
              }
            }
          }
        }

        // 2. Attraction along edges
        const nodeMap = new Map(next.map((n) => [n.id, n]));
        for (const edge of edges) {
          const u = nodeMap.get(edge.source);
          const v = nodeMap.get(edge.target);
          if (u && v) {
            const dx = v.x - u.x;
            const dy = v.y - u.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const targetDist = 120;
            const force = (dist - targetDist) * kAttract;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;

            if (u.id !== draggedNodeId) {
              u.vx += fx;
              u.vy += fy;
            }
            if (v.id !== draggedNodeId) {
              v.vx -= fx;
              v.vy -= fy;
            }
          }
        }

        // 3. Center gravity force
        for (const n of next) {
          if (n.id === draggedNodeId) continue;
          n.vx -= n.x * 0.01;
          n.vy -= n.y * 0.01;
          n.x += n.vx;
          n.y += n.vy;
          n.vx *= damping;
          n.vy *= damping;
        }

        return next;
      });

      iteration++;
      if (iteration < maxIterations || draggedNodeId !== null) {
        animId = requestAnimationFrame(tick);
      }
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [edges, draggedNodeId]);

  // Center on selected node if camera is off
  const centerOnNode = useCallback((nodeId: string) => {
    const target = simNodes.find((n) => n.id === nodeId);
    if (!target || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    setTransform((prev) => ({
      ...prev,
      x: centerX - target.x * prev.k,
      y: centerY - target.y * prev.k,
    }));
  }, [simNodes]);

  // Pan handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.target === containerRef.current || (e.target as HTMLElement).tagName === "svg") {
      setIsPanning(true);
      setStartPan({ x: e.clientX - transform.x, y: e.clientY - transform.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isPanning) {
      setTransform((prev) => ({
        ...prev,
        x: e.clientX - startPan.x,
        y: e.clientY - startPan.y,
      }));
    } else if (draggedNodeId) {
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;
      const mouseX = (e.clientX - rect.left - transform.x) / transform.k;
      const mouseY = (e.clientY - rect.top - transform.y) / transform.k;

      setSimNodes((prev) =>
        prev.map((n) => (n.id === draggedNodeId ? { ...n, x: mouseX, y: mouseY, vx: 0, vy: 0 } : n))
      );
    }
  };

  const handleMouseUp = () => {
    setIsPanning(false);
    setDraggedNodeId(null);
  };

  // Zoom handlers
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    const newK = Math.max(0.2, Math.min(4.0, transform.k * zoomFactor));

    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;

    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    // Zoom towards mouse cursor
    const newX = mouseX - (mouseX - transform.x) * (newK / transform.k);
    const newY = mouseY - (mouseY - transform.y) * (newK / transform.k);

    setTransform({ x: newX, y: newY, k: newK });
  };

  const handleZoom = (delta: number) => {
    const newK = Math.max(0.2, Math.min(4.0, transform.k + delta));
    setTransform((prev) => ({ ...prev, k: newK }));
  };

  const handleResetView = () => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    setTransform({
      x: rect.width / 2,
      y: rect.height / 2,
      k: 1.0,
    });
  };

  // Neighborhood connected node IDs
  const connectedNodeIds = useMemo(() => {
    if (!selectedNodeId) return new Set<string>();
    const set = new Set<string>([selectedNodeId]);
    for (const edge of edges) {
      if (edge.source === selectedNodeId) set.add(edge.target);
      if (edge.target === selectedNodeId) set.add(edge.source);
    }
    return set;
  }, [selectedNodeId, edges]);

  const simNodeMap = useMemo(() => new Map(simNodes.map((n) => [n.id, n])), [simNodes]);

  return (
    <div
      ref={containerRef}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onWheel={handleWheel}
      className="relative w-full h-[550px] bg-slate-950 rounded-2xl overflow-hidden cursor-grab active:cursor-grabbing select-none border border-slate-800 shadow-inner"
    >
      {/* Zoom / Navigation Floating Toolbar */}
      <div className="absolute top-4 right-4 z-20 flex flex-col gap-1.5 bg-slate-900/90 backdrop-blur p-1.5 rounded-xl border border-slate-700 shadow-lg">
        <button
          onClick={() => handleZoom(0.2)}
          title="Zoom In"
          aria-label="Zoom in"
          className="w-8 h-8 flex items-center justify-center text-slate-200 hover:bg-slate-800 hover:text-white rounded-lg text-lg font-bold transition"
        >
          +
        </button>
        <button
          onClick={() => handleZoom(-0.2)}
          title="Zoom Out"
          aria-label="Zoom out"
          className="w-8 h-8 flex items-center justify-center text-slate-200 hover:bg-slate-800 hover:text-white rounded-lg text-lg font-bold transition"
        >
          −
        </button>
        <button
          onClick={handleResetView}
          title="Reset View"
          aria-label="Reset graph view"
          className="w-8 h-8 flex items-center justify-center text-slate-200 hover:bg-slate-800 hover:text-white rounded-lg text-xs font-semibold transition"
        >
          ⤢
        </button>
        {selectedNodeId && (
          <button
            onClick={() => centerOnNode(selectedNodeId)}
            title="Center on Selected Node"
            aria-label="Center on selected node"
            className="w-8 h-8 flex items-center justify-center text-primary hover:bg-surface-container-high hover:text-luminous-highlight rounded-lg text-sm transition"
          >
            🎯
          </button>
        )}
      </div>

      {/* Canvas SVG */}
      <svg className="w-full h-full">
        <defs>
          {/* Arrow markers */}
          <marker
            id="arrow-prereq"
            viewBox="0 -5 10 10"
            refX="22"
            refY="0"
            markerWidth="6"
            markerHeight="6"
            orient="auto"
          >
            <path d="M0,-5L10,0L0,5" fill="#6366f1" />
          </marker>
          <marker
            id="arrow-path"
            viewBox="0 -5 10 10"
            refX="22"
            refY="0"
            markerWidth="7"
            markerHeight="7"
            orient="auto"
          >
            <path d="M0,-5L10,0L0,5" fill="#10b981" />
          </marker>
          <marker
            id="arrow-default"
            viewBox="0 -5 10 10"
            refX="22"
            refY="0"
            markerWidth="5"
            markerHeight="5"
            orient="auto"
          >
            <path d="M0,-5L10,0L0,5" fill="#64748b" />
          </marker>
        </defs>

        <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.k})`}>
          {/* 1. EDGES */}
          {edges.map((edge, idx) => {
            const u = simNodeMap.get(edge.source);
            const v = simNodeMap.get(edge.target);
            if (!u || !v) return null;

            const isHighlightedEdge =
              highlightPathIds.includes(edge.source) && highlightPathIds.includes(edge.target);

            const isConnectedToSelected =
              selectedNodeId && (edge.source === selectedNodeId || edge.target === selectedNodeId);

            const isDimmed =
              selectedNodeId && !isConnectedToSelected && !isHighlightedEdge;

            const strokeColor = isHighlightedEdge
              ? "#10b981"
              : edge.type === "prerequisite_of"
              ? "#6366f1"
              : edge.type === "taught_in"
              ? "#f59e0b"
              : "#475569";

            const markerEnd = isHighlightedEdge
              ? "url(#arrow-path)"
              : edge.type === "prerequisite_of"
              ? "url(#arrow-prereq)"
              : "url(#arrow-default)";

            return (
              <line
                key={idx}
                x1={u.x}
                y1={u.y}
                x2={v.x}
                y2={v.y}
                stroke={strokeColor}
                strokeWidth={isHighlightedEdge ? 3 : isConnectedToSelected ? 2.2 : 1.2}
                strokeDasharray={edge.type === "related_to" ? "4,4" : undefined}
                markerEnd={edge.type !== "related_to" ? markerEnd : undefined}
                opacity={isDimmed ? 0.15 : 0.85}
                className="transition-opacity duration-300"
              />
            );
          })}

          {/* 2. NODES */}
          {simNodes.map((node) => {
            const isSelected = selectedNodeId === node.id;
            const isConnected = connectedNodeIds.has(node.id);
            const isPathNode = highlightPathIds.includes(node.id);
            const isDimmed = selectedNodeId && !isConnected && !isPathNode;

            const nodeColor =
              node.type === "subject"
                ? "#8b5cf6"
                : node.type === "chapter"
                ? "#f59e0b"
                : node.type === "document"
                ? "#10b981"
                : "#4f46e5";

            const ringColor =
              node.mastery_score >= 0.8
                ? "#10b981"
                : node.mastery_score >= 0.5
                ? "#3b82f6"
                : node.mastery_score > 0
                ? "#f43f5e"
                : "#334155";

            return (
              <g
                key={node.id}
                transform={`translate(${node.x}, ${node.y})`}
                onMouseDown={(e) => {
                  e.stopPropagation();
                  setDraggedNodeId(node.id);
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectNode(node);
                }}
                className="cursor-pointer group"
                opacity={isDimmed ? 0.2 : 1.0}
              >
                {/* Mastery Indicator Outer Ring */}
                <circle
                  r={node.radius + 3}
                  fill="none"
                  stroke={ringColor}
                  strokeWidth={isSelected ? 3.5 : 2}
                  strokeDasharray={isSelected ? "3,3" : undefined}
                  className="transition-all duration-300"
                />

                {/* Node Core Body */}
                <circle
                  r={node.radius}
                  fill={nodeColor}
                  stroke={isSelected ? "#ffffff" : "#0f172a"}
                  strokeWidth={2}
                  className="group-hover:brightness-125 transition"
                />

                {/* Node Type Emoji or Initial */}
                <text
                  textAnchor="middle"
                  dy=".3em"
                  fill="#ffffff"
                  fontSize={node.radius * 0.75}
                  fontWeight="bold"
                  pointerEvents="none"
                >
                  {node.type === "document"
                    ? "📄"
                    : node.type === "chapter"
                    ? "📚"
                    : node.type === "subject"
                    ? "🏛️"
                    : "💡"}
                </text>

                {/* Node Label Text */}
                <text
                  y={node.radius + 14}
                  textAnchor="middle"
                  fill={isSelected ? "#a5b4fc" : "#e2e8f0"}
                  fontSize={11}
                  fontWeight={isSelected ? "bold" : "normal"}
                  pointerEvents="none"
                  className="drop-shadow-md select-none"
                >
                  {node.label.length > 22 ? `${node.label.slice(0, 20)}…` : node.label}
                </text>

                {/* Mastery Badge (if > 0) */}
                {node.mastery_score > 0 && (
                  <text
                    y={-node.radius - 6}
                    textAnchor="middle"
                    fill="#34d399"
                    fontSize={9}
                    fontWeight="bold"
                    pointerEvents="none"
                  >
                    {Math.round(node.mastery_score * 100)}%
                  </text>
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {/* Instruction Overlay Banner */}
      <div className="absolute bottom-3 left-4 z-10 text-[11px] text-slate-400 bg-slate-900/80 backdrop-blur px-3 py-1.5 rounded-lg border border-slate-800 pointer-events-none">
        🖱️ <b>Pan:</b> Drag background · <b>Zoom:</b> Mouse wheel · <b>Move:</b> Drag node · <b>Select:</b> Click node
      </div>
    </div>
  );
}
