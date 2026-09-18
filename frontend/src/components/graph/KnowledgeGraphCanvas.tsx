import React, { useEffect, useRef, useState, useMemo, useCallback } from "react";
import { GraphNode, GraphEdge } from "../../api/graph";
import { useGraphSimulation } from "../../hooks/useGraphSimulation";

interface Point {
  x: number;
  y: number;
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

  // Positions come from the simulation hook; this component owns only the
  // camera, the pointer interactions and the SVG.
  const { simNodes, setNodePosition, hasSettled } = useGraphSimulation(
    nodes,
    edges,
    draggedNodeId,
  );


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

      setNodePosition(draggedNodeId, mouseX, mouseY);
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

  // Text is half of every node's markup -- an emoji, a label and a mastery
  // badge against two circles -- and on a large graph zoomed out to fit, all
  // three render at well under a pixel. Dropping them there is not a
  // compromise: nothing legible is lost, and the node count that makes them
  // expensive is exactly the count that makes them unreadable.
  //
  // Gated on node count as well as zoom so an ordinary graph is never affected:
  // a 26-node graph sits around k=0.56 when framed, which would otherwise put
  // it the wrong side of the threshold.
  const showNodeText = simNodes.length <= 150 || transform.k >= 0.35;

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
          {/* Arrow markers.
              markerUnits is userSpaceOnUse so the head is sized in graph
              units rather than multiples of the line's stroke width: at a
              1.2 stroke the default put a seven-unit arrow under a
              twenty-unit node, which is why no edge ever appeared to have a
              direction. refX sits on the tip, and each line stops short of
              its target, so the head lands just outside the circle. */}
          <marker
            id="arrow-prereq"
            viewBox="0 -5 10 10"
            refX="10"
            refY="0"
            markerUnits="userSpaceOnUse"
            markerWidth="13"
            markerHeight="13"
            orient="auto"
          >
            <path d="M0,-5L10,0L0,5" fill="#6366f1" />
          </marker>
          <marker
            id="arrow-path"
            viewBox="0 -5 10 10"
            refX="10"
            refY="0"
            markerUnits="userSpaceOnUse"
            markerWidth="15"
            markerHeight="15"
            orient="auto"
          >
            <path d="M0,-5L10,0L0,5" fill="#10b981" />
          </marker>
          <marker
            id="arrow-default"
            viewBox="0 -5 10 10"
            refX="10"
            refY="0"
            markerUnits="userSpaceOnUse"
            markerWidth="11"
            markerHeight="11"
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

            // Between the rims, not the centres: an arrowhead drawn at the
            // target's centre sits underneath the node and cannot be seen,
            // so which way round a prerequisite goes was never shown.
            const dx = v.x - u.x;
            const dy = v.y - u.y;
            const distance = Math.hypot(dx, dy) || 1;
            const unitX = dx / distance;
            const unitY = dy / distance;
            const headroom = u.radius + v.radius + 14;
            // Overlapping nodes leave no room to trim; a trimmed line there
            // would double back on itself and point the wrong way.
            const trimmed = distance > headroom;
            const x1 = trimmed ? u.x + unitX * (u.radius + 2) : u.x;
            const y1 = trimmed ? u.y + unitY * (u.radius + 2) : u.y;
            const x2 = trimmed ? v.x - unitX * (v.radius + 3) : v.x;
            const y2 = trimmed ? v.y - unitY * (v.radius + 3) : v.y;

            const markerEnd = isHighlightedEdge
              ? "url(#arrow-path)"
              : edge.type === "prerequisite_of"
              ? "url(#arrow-prereq)"
              : "url(#arrow-default)";

            return (
              <line
                key={idx}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke={strokeColor}
                strokeWidth={isHighlightedEdge ? 3 : isConnectedToSelected ? 2.2 : 1.2}
                strokeDasharray={edge.type === "related_to" ? "4,4" : undefined}
                // Stroke width in screen pixels, not graph units. A whole
                // curriculum framed to fit sits near k=0.24, where a 1.2
                // unit line is a quarter of a pixel: every edge was being
                // drawn and none of them could be seen.
                vectorEffect="non-scaling-stroke"
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
                {showNodeText && (
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
                )}

                {/* Node Label Text */}
                {showNodeText && (
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
                )}

                {/* Mastery Badge (if > 0) */}
                {showNodeText && node.mastery_score > 0 && (
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
