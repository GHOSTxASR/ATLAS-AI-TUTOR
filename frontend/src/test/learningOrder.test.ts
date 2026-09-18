import { describe, expect, it } from "vitest";

import { learningOrder } from "../hooks/useGraphSimulation";
import type { GraphEdge, GraphNode } from "../api/graph";

/**
 * The seeded layout only reads as a sequence if the sequence it is given is
 * one. A curriculum interleaved with an unrelated cluster -- which is what a
 * plain topological sort produces when several chains start at once -- would
 * lay the course out in pieces.
 */

const node = (id: string): GraphNode =>
  ({
    id,
    label: id,
    type: "concept",
    profile_id: "p",
    mastery_score: 0,
    mention_count: 1,
    first_seen: "",
    last_seen: "",
    document_ids: [],
    chat_session_ids: [],
  }) as unknown as GraphNode;

const before = (source: string, target: string): GraphEdge =>
  ({ source, target, type: "prerequisite_of", weight: 1, created_at: "" }) as unknown as GraphEdge;

describe("learningOrder", () => {
  it("follows a chain from its start to its end", () => {
    const nodes = [node("b"), node("c"), node("a")];
    const edges = [before("a", "b"), before("b", "c")];

    expect(learningOrder(nodes, edges)).toEqual(["a", "b", "c"]);
  });

  it("keeps two separate chains in one piece each", () => {
    // Both start with nothing before them, so they compete to go first.
    const nodes = ["a1", "a2", "a3", "b1", "b2", "b3"].map(node);
    const edges = [
      before("a1", "a2"),
      before("a2", "a3"),
      before("b1", "b2"),
      before("b2", "b3"),
    ];

    const order = learningOrder(nodes, edges);
    const a = order.filter((id) => id.startsWith("a"));
    const b = order.filter((id) => id.startsWith("b"));
    expect(a).toEqual(["a1", "a2", "a3"]);
    expect(b).toEqual(["b1", "b2", "b3"]);
    // Contiguous: one chain finishes before the other begins.
    expect(order.indexOf("a3")).toBe(order.indexOf("a1") + 2);
    expect(order.indexOf("b3")).toBe(order.indexOf("b1") + 2);
  });

  it("places unconnected concepts too, rather than dropping them", () => {
    const nodes = [node("a"), node("b"), node("loose")];
    const order = learningOrder(nodes, [before("a", "b")]);

    expect(order).toHaveLength(3);
    expect(order).toContain("loose");
  });

  it("does not hang on a cycle", () => {
    const nodes = [node("a"), node("b"), node("c")];
    const edges = [before("a", "b"), before("b", "c"), before("c", "a")];

    const order = learningOrder(nodes, edges);
    expect([...order].sort()).toEqual(["a", "b", "c"]);
  });

  it("says there is no order when nothing is a prerequisite of anything", () => {
    const nodes = [node("a"), node("b")];
    const edges = [
      { source: "a", target: "b", type: "related_to", weight: 1, created_at: "" } as unknown as GraphEdge,
    ];

    // Empty, so seeding keeps the ring it always used.
    expect(learningOrder(nodes, edges)).toEqual([]);
  });
});
