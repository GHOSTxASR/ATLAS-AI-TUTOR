import { useEffect, useState } from "react";

import { GraphEdge, GraphNode } from "../api/graph";

export interface SimulatedNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
}

/**
 * Force-directed layout for the knowledge graph.
 *
 * Lives apart from the canvas because it shares nothing with rendering: it owns
 * positions and velocities, the canvas owns pan, zoom, selection and the SVG.
 * Keeping them in one component meant 190 lines of physics sat between the
 * state declarations and the markup that used them.
 *
 * Returns the simulated nodes, a setter the canvas uses while dragging, and
 * whether the layout has come to rest -- which is the cue to frame the graph.
 */
export function useGraphSimulation(
  nodes: GraphNode[],
  edges: GraphEdge[],
  draggedNodeId: string | null,
) {
  const [simNodes, setSimNodes] = useState<SimulatedNode[]>([]);
  const [hasSettled, setHasSettled] = useState(false);

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

  return { simNodes, setSimNodes, hasSettled };
}
