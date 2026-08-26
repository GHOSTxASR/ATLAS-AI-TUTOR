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
  const [hasSettled, setHasSettled] = useState(false);

  // Simulated node positions
  const [simNodes, setSimNodes] = useState<SimulatedNode[]>([]);

  // Initialize simulation positions in a ring/circle layout
  useEffect(() => {
    if (nodes.length === 0) {
      setSimNodes([]);
      return;
    }

    // Seed on a ring big enough to hold the nodes without overlap, so the
    // simulation refines a layout instead of untangling a knot.
    const radiusBase = Math.max(160, (nodes.length * 46) / (2 * Math.PI));

    // Previous positions come from the updater rather than the closure: a node
    // that is still present should stay where the simulation put it, and
    // reading that from state would either go stale or, if depended on, restart
    // seeding every time seeding wrote.
    setSimNodes((previous) =>
      nodes.map((node, i) => {
        const radius = Math.min(36, Math.max(18, 16 + (node.mention_count || 1) * 2));
        const existing = previous.find((sn) => sn.id === node.id);
        if (existing) {
          return { ...existing, ...node, radius };
        }
        const angle = (i / nodes.length) * 2 * Math.PI;
        return {
          ...node,
          x: Math.cos(angle) * radiusBase + (Math.random() - 0.5) * 40,
          y: Math.sin(angle) * radiusBase + (Math.random() - 0.5) * 40,
          vx: 0,
          vy: 0,
          radius,
        };
      }),
    );
  }, [nodes]);

  // Run force-directed physics iteration
  useEffect(() => {
    if (simNodes.length === 0) return;

    let animId: number;
    let iteration = 0;
    // 80 ticks stopped the layout mid-spread on anything but a tiny graph.
    // Settling is detected below, so a simple graph still stops early.
    const maxIterations = 400;
    let settled = false;
    setHasSettled(false);

    const tick = () => {
      setSimNodes((currentNodes) => {
        if (currentNodes.length === 0) return currentNodes;
        const next = currentNodes.map((n) => ({ ...n }));
        // Repulsion falls off with distance squared while the old centre
        // gravity grew linearly with it, so gravity won everywhere that
        // mattered: at 300px out it pulled 3.0 against 0.09 of push, and the
        // graph collapsed into a ball. Repulsion is now strong enough to hold
        // a gap open, and gravity is weak and only there to stop disconnected
        // nodes drifting off screen.
        //
        // Repulsion also scales with node count: the same constant that spaces
        // 9 nodes leaves 200 overlapping.
        const kRepulse = 9000 * Math.max(1, Math.sqrt(next.length / 12));
        const kAttract = 0.05;
        const kGravity = 0.004;
        const damping = 0.85;

        // 1. Repulsion between all node pairs
        for (let i = 0; i < next.length; i++) {
          for (let j = i + 1; j < next.length; j++) {
            const dx = next[i].x - next[j].x;
            const dy = next[i].y - next[j].y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            if (dist < 700) {
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
            const targetDist = 150;
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
          n.vx -= n.x * kGravity;
          n.vy -= n.y * kGravity;
          n.x += n.vx;
          n.y += n.vy;
          n.vx *= damping;
          n.vy *= damping;
        }

        // 4. Separate overlaps directly.
        //    Repulsion alone never resolved these: an edge pulling two nodes
        //    together balances against it at a distance smaller than the two
        //    radii, so linked pairs settled on top of each other. Moving the
        //    positions apart is unconditional and cannot be out-pulled.
        const PADDING = 14;
        for (let pass = 0; pass < 3; pass++) {
          for (let i = 0; i < next.length; i++) {
            for (let j = i + 1; j < next.length; j++) {
              const a = next[i];
              const b = next[j];
              const minDist = a.radius + b.radius + PADDING;
              let dx = b.x - a.x;
              let dy = b.y - a.y;
              let dist = Math.sqrt(dx * dx + dy * dy);
              if (dist >= minDist) continue;
              if (dist < 0.01) {
                // Exactly coincident: pick an arbitrary axis to break the tie.
                dx = Math.random() - 0.5;
                dy = Math.random() - 0.5;
                dist = Math.sqrt(dx * dx + dy * dy) || 1;
              }
              const shift = (minDist - dist) / 2;
              const ux = (dx / dist) * shift;
              const uy = (dy / dist) * shift;
              if (a.id !== draggedNodeId) {
                a.x -= ux;
                a.y -= uy;
              }
              if (b.id !== draggedNodeId) {
                b.x += ux;
                b.y += uy;
              }
            }
          }
        }

        // Stop once nothing is really moving rather than burning the full
        // iteration budget every time.
        const energy = next.reduce((sum, n) => sum + Math.abs(n.vx) + Math.abs(n.vy), 0);
        settled = energy / Math.max(1, next.length) < 0.04;

        return next;
      });

      iteration++;
      if ((iteration < maxIterations && !settled) || draggedNodeId !== null) {
        animId = requestAnimationFrame(tick);
      } else {
        setHasSettled(true);
      }
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
    // simNodes.length, not simNodes: the effect bails when there are no nodes
    // yet, so it has to re-run once they are seeded -- otherwise whether the
    // layout ever ran came down to a race between the seed effect and the
    // edges arriving, and a graph that lost that race rendered the raw seed
    // ring with nodes still overlapping. The length rather than the array
    // because the array identity changes on every tick, which would restart
    // the simulation forever.
    // simNodes.length rather than simNodes: the simulation rewrites the array
    // every tick, so depending on its identity would restart the loop each
    // frame. The count is what this effect reacts to -- it bails when there are
    // no nodes, so it must re-run once they are seeded.
  }, [edges, draggedNodeId, simNodes.length]);

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

  // Zoom is bound natively rather than through React's onWheel, because React
  // registers wheel listeners as passive: preventDefault() inside one is a
  // silent no-op. A trackpad pinch arrives as a wheel event with ctrlKey set,
  // so the browser's own page zoom ran instead of the graph's -- the whole page
  // scaled while the graph sat still.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();

      const rect = el.getBoundingClientRect();
      const pointerX = e.clientX - rect.left;
      const pointerY = e.clientY - rect.top;

      setTransform((prev) => {
        // Scale with the gesture rather than a fixed step, so a pinch tracks the
        // fingers and a notched wheel moves a sensible amount. A pinch arrives
        // as many small ctrlKey deltas, so its per-event multiplier has to stay
        // low or a single gesture slams into the zoom clamp; a mouse notch
        // arrives once at deltaY 100-120 and wants roughly 1.2x.
        const intensity = e.ctrlKey ? 0.01 : 0.0016;
        const factor = Math.exp(-e.deltaY * intensity);
        const nextK = Math.max(0.2, Math.min(4.0, prev.k * factor));
        if (nextK === prev.k) return prev;

        // Keep the point under the pointer fixed while scaling.
        const ratio = nextK / prev.k;
        return {
          k: nextK,
          x: pointerX - (pointerX - prev.x) * ratio,
          y: pointerY - (pointerY - prev.y) * ratio,
        };
      });
    };

    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const handleZoom = (delta: number) => {
    const newK = Math.max(0.2, Math.min(4.0, transform.k + delta));
    setTransform((prev) => ({ ...prev, k: newK }));
  };

  // Frames the whole graph rather than just recentring at 1:1. The old version
  // set k to 1 and the origin to the middle, which on any graph wider than the
  // panel left nodes cut off at the edges with no hint they were there.
  const handleResetView = useCallback(() => {
    const el = containerRef.current;
    if (!el || simNodes.length === 0) return;
    const rect = el.getBoundingClientRect();

    const pad = 70;
    const xs = simNodes.map((n) => n.x);
    const ys = simNodes.map((n) => n.y);
    const minX = Math.min(...xs) - pad;
    const maxX = Math.max(...xs) + pad;
    const minY = Math.min(...ys) - pad;
    const maxY = Math.max(...ys) + pad;

    const k = Math.max(
      0.2,
      Math.min(1.4, Math.min(rect.width / (maxX - minX), rect.height / (maxY - minY))),
    );
    setTransform({
      k,
      x: rect.width / 2 - ((minX + maxX) / 2) * k,
      y: rect.height / 2 - ((minY + maxY) / 2) * k,
    });
  }, [simNodes]);

  // Frame the graph once, the first time a given node set finishes settling.
  // Guarded by a ref so it never yanks the view back after the user has panned
  // or zoomed themselves.
  const autoFittedFor = useRef<number>(-1);
  useEffect(() => {
    if (!hasSettled || simNodes.length === 0) return;
    if (autoFittedFor.current === simNodes.length) return;
    autoFittedFor.current = simNodes.length;
    handleResetView();
  }, [hasSettled, simNodes.length, handleResetView]);

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
      style={{ touchAction: "none", overscrollBehavior: "contain" }}
      className="relative w-full h-[550px] bg-surface-container-lowest overflow-hidden cursor-grab active:cursor-grabbing select-none border border-glass-border shadow-inner"
    >
      {/* Zoom / Navigation Floating Toolbar */}
      <div className="absolute top-4 right-4 z-20 flex flex-col gap-1.5 bg-surface-container/90 backdrop-blur p-1.5 border border-glass-border shadow-lg">
        <button
          onClick={() => handleZoom(0.2)}
          title="Zoom In"
          aria-label="Zoom in"
          className="w-8 h-8 flex items-center justify-center text-on-surface hover:bg-surface-container-high hover:text-on-surface text-lg font-bold transition"
        >
          +
        </button>
        <button
          onClick={() => handleZoom(-0.2)}
          title="Zoom Out"
          aria-label="Zoom out"
          className="w-8 h-8 flex items-center justify-center text-on-surface hover:bg-surface-container-high hover:text-on-surface text-lg font-bold transition"
        >
          −
        </button>
        <button
          onClick={handleResetView}
          title="Reset View"
          aria-label="Reset graph view"
          className="atlas-btn"
        >
          ⤢
        </button>
        {selectedNodeId && (
          <button
            onClick={() => centerOnNode(selectedNodeId)}
            title="Center on Selected Node"
            aria-label="Center on selected node"
            className="w-8 h-8 flex items-center justify-center text-primary hover:bg-surface-container-high hover:text-luminous-highlight text-sm transition"
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
                  stroke={isSelected ? "#ffffff" : "#111113"}
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
      <div className="absolute bottom-3 left-4 z-10 text-[11px] text-on-surface-variant bg-surface-container/80 backdrop-blur px-3 py-1.5 border border-glass-border pointer-events-none">
        🖱️ <b>Pan:</b> Drag background · <b>Zoom:</b> Mouse wheel · <b>Move:</b> Drag node · <b>Select:</b> Click node
      </div>
    </div>
  );
}
