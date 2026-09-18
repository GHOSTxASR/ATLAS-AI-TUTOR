import { useCallback, useEffect, useRef, useState } from "react";

import { GraphEdge, GraphNode } from "../api/graph";

export interface SimulatedNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
}

/**
 * Above this many nodes, publishing to React every frame costs more than the
 * physics does.
 *
 * Measured on a 1,300-node graph: the force step is ~11ms a frame, but the
 * re-render of 1,300 nodes -- six SVG elements each -- takes ~60ms, so the
 * layout ran at 14fps for 20 seconds before settling. Below this threshold the
 * per-frame cost is irrelevant and the layout commits every frame exactly as
 * it always did.
 */
const LARGE_GRAPH_NODES = 150;

/**
 * How often a large graph publishes positions while the layout is running.
 *
 * The simulation still steps every frame -- skipping steps would change the
 * layout it converges to. Only the hand-off to React is throttled, so the
 * result is identical and the animation is a lower frame rate rather than a
 * different shape.
 *
 * Has to be comfortably longer than a commit takes, or it saves nothing: a
 * commit on a 1,300-node graph costs ~48ms, so an 80ms interval still spent
 * one frame in two rendering. At 250ms the physics gets four or five frames
 * to itself between publishes, which is what brings the layout down to being
 * bound by the simulation rather than by React.
 */
const COMMIT_INTERVAL_MS = 250;

/**
 * The order the graph is meant to be learned in, read off its own edges.
 *
 * Chains are followed to their end before the next one is started, so a run
 * of topics stays a run rather than being interleaved with an unrelated one
 * -- which is what a plain topological sort would do with a curriculum and a
 * handful of loose clusters sitting side by side.
 *
 * Everything else lands at the end, in the order it arrived.
 */
export function learningOrder(nodes: GraphNode[], edges: GraphEdge[]): string[] {
  const successors = new Map<string, string[]>();
  const incoming = new Map<string, number>();
  for (const node of nodes) incoming.set(node.id, 0);

  let ordered = false;
  for (const edge of edges) {
    if (edge.type !== "prerequisite_of") continue;
    if (!incoming.has(edge.source) || !incoming.has(edge.target)) continue;
    ordered = true;
    const from = successors.get(edge.source);
    if (from) from.push(edge.target);
    else successors.set(edge.source, [edge.target]);
    incoming.set(edge.target, (incoming.get(edge.target) ?? 0) + 1);
  }
  if (!ordered) return [];

  const order: string[] = [];
  const seen = new Set<string>();

  const walk = (startId: string) => {
    let current: string | undefined = startId;
    while (current && !seen.has(current)) {
      seen.add(current);
      order.push(current);
      current = (successors.get(current) ?? []).find((id) => !seen.has(id));
    }
  };

  // Begin where nothing comes first: the start of each chain.
  for (const node of nodes) {
    if (!seen.has(node.id) && (incoming.get(node.id) ?? 0) === 0) walk(node.id);
  }
  // Whatever is left is inside a loop, or was only ever something's target.
  for (const node of nodes) if (!seen.has(node.id)) walk(node.id);

  return order;
}

/**
 * Distance between neighbours along the seeded spiral.
 *
 * Matched to the rest length of the edge springs, so a chain starts at the
 * length it wants to be and the layout refines it instead of first having to
 * stretch or squash every link in the curriculum.
 */
const SEED_SPACING = 150;

/**
 * Distance between one turn of the spiral and the next.
 *
 * Two node-spacings apart: closer and repulsion shuffles neighbouring turns
 * into each other, taking the ordering with them; much wider and the graph
 * opens out into a disc far larger than it needs.
 */
const SEED_TURN_GAP = SEED_SPACING * 2;

/** How far out the seeded spiral reaches for a graph of this size. */
function seedExtent(count: number): number {
  const growth = SEED_TURN_GAP / (2 * Math.PI);
  return Math.sqrt(2 * Math.max(1, count - 1) * SEED_SPACING * growth);
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

  // The positions the simulation actually works on. Physics mutates this in
  // place and publishes a copy to state on a schedule; keeping it out of state
  // is what lets the two run at different rates.
  const workingRef = useRef<SimulatedNode[]>([]);

  /** Publish the working positions to React. */
  const commit = useCallback(() => {
    setSimNodes(workingRef.current.map((n) => ({ ...n })));
  }, []);

  // Initialize simulation positions in a ring/circle layout
  useEffect(() => {
    if (nodes.length === 0) {
      workingRef.current = [];
      setSimNodes([]);
      return;
    }

    // Seed in the order the material is meant to be studied, running outward
    // along a spiral, so what the layout settles into follows the sequence.
    //
    // A ring was the same idea without the direction: neighbours sat next to
    // each other, but it closed on itself, so a curriculum came out as a
    // starburst with no beginning and nothing to follow. A force layout keeps
    // roughly the arrangement it is handed, which is what makes the starting
    // positions worth choosing rather than scattering.
    const sequence = learningOrder(nodes, edges);
    const seedRank = new Map(sequence.map((id, index) => [id, index]));

    // r = b * theta, stepped by arc length so neighbours stay one spacing
    // apart however far out the turn is.
    const growth = SEED_TURN_GAP / (2 * Math.PI);
    const spiralAt = (rank: number) => {
      const theta = Math.sqrt((2 * rank * SEED_SPACING) / growth);
      const radius = growth * theta;
      return { x: Math.cos(theta) * radius, y: Math.sin(theta) * radius };
    };

    // Nothing to sequence -- no prerequisites anywhere -- so keep the ring.
    const radiusBase = Math.max(160, (nodes.length * 46) / (2 * Math.PI));

    // Previous positions come from the updater rather than the closure: a node
    // that is still present should stay where the simulation put it, and
    // reading that from state would either go stale or, if depended on, restart
    // seeding every time seeding wrote.
    setSimNodes((previous) => {
      const seeded = nodes.map((node, i) => {
        const radius = Math.min(36, Math.max(18, 16 + (node.mention_count || 1) * 2));
        const existing = previous.find((sn) => sn.id === node.id);
        if (existing) {
          return { ...existing, ...node, radius };
        }
        const rank = seedRank.get(node.id);
        const angle = (i / nodes.length) * 2 * Math.PI;
        const seat =
          rank === undefined
            ? { x: Math.cos(angle) * radiusBase, y: Math.sin(angle) * radiusBase }
            : spiralAt(rank);
        return {
          ...node,
          // A little scatter, so nothing starts perfectly symmetrical and
          // sits there with every force cancelling out.
          x: seat.x + (Math.random() - 0.5) * 40,
          y: seat.y + (Math.random() - 0.5) * 40,
          vx: 0,
          vy: 0,
          radius,
        };
      });
      // The physics works from its own copy, so seeding has to hand it one.
      workingRef.current = seeded.map((n) => ({ ...n }));
      return seeded;
    });
  }, [nodes, edges]);

  // Run force-directed physics iteration
  useEffect(() => {
    if (simNodes.length === 0) return;

    let animId: number;
    let iteration = 0;
    // 80 ticks stopped the layout mid-spread on anything but a tiny graph.
    // Settling is detected below, so a simple graph still stops early.
    const maxIterations = 400;
    let settled = false;
    // A small graph publishes every frame, exactly as before; only a large one
    // is throttled, and only while it is still moving.
    const throttleCommits = simNodes.length > LARGE_GRAPH_NODES;
    let lastCommit = 0;
    setHasSettled(false);

    const tick = (now: number) => {
      {
        const next = workingRef.current;
        if (next.length === 0) return;
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
        // Just enough room for the seeded arrangement to keep its shape.
        // With more slack than this the graph inflates against the boundary
        // -- 179 nodes seeded to 1600 spread to 2125 before stopping -- which
        // buys nothing and only makes the whole thing harder to take in.
        const containment = seedExtent(next.length) * 1.05;

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

        // 3. Containment, in place of centre gravity
        //
        // Gravity used to pull every node inward in proportion to how far out
        // it was, which fixes the size of the graph no matter how it started:
        // 179 nodes settled into a disc of radius ~1100 whatever was seeded,
        // and a spiral laid out to 1600 was squeezed into that same disc with
        // its ordering lost on the way in. What gravity is actually for --
        // its comment says so -- is keeping unconnected nodes from drifting
        // off screen, and a boundary does that without flattening what is
        // inside it.
        const boundary = containment;
        for (const n of next) {
          if (n.id === draggedNodeId) continue;
          const distance = Math.sqrt(n.x * n.x + n.y * n.y);
          if (distance > boundary) {
            // Proportional to the overshoot, so it is nothing at the edge and
            // firm well past it.
            const pull = (kGravity * (distance - boundary)) / distance;
            n.vx -= n.x * pull;
            n.vy -= n.y * pull;
          }
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
      }

      iteration++;
      const finished = (iteration >= maxIterations || settled) && draggedNodeId === null;

      // Always publish the final frame, so the layout the user is left looking
      // at is the one the physics actually reached.
      if (!throttleCommits || finished || now - lastCommit >= COMMIT_INTERVAL_MS) {
        lastCommit = now;
        commit();
      }

      if (!finished) {
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
  }, [edges, draggedNodeId, simNodes.length, commit]);

  /**
   * Move one node, as dragging does.
   *
   * Writes to the working copy as well as to state: the physics reads from the
   * working copy, so updating only React would have the next simulation frame
   * overwrite the drag and the node would spring back under the cursor.
   */
  const setNodePosition = useCallback((id: string, x: number, y: number) => {
    const node = workingRef.current.find((n) => n.id === id);
    if (node) {
      node.x = x;
      node.y = y;
      node.vx = 0;
      node.vy = 0;
    }
    setSimNodes((prev) =>
      prev.map((n) => (n.id === id ? { ...n, x, y, vx: 0, vy: 0 } : n)),
    );
  }, []);

  return { simNodes, setNodePosition, hasSettled };
}
