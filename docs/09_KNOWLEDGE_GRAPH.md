# 09. Knowledge Graph

## 1. Knowledge Graph Overview
The Knowledge Graph is a structured, semantic representation of the user's learning domain. While the Memory System tracks *how* the user learns, the Knowledge Graph tracks *what* the user learns. It grows automatically as documents are ingested and chats occur, mapping out concepts, prerequisites, and the user's mastery of each node.

## 2. Graph Data Model
The graph is composed of **Nodes** (entities/concepts) and **Edges** (relationships between nodes). It is a Directed Graph (DiGraph).

## 3. Node Types
1.  **concept**: A specific idea or skill (e.g., "Backpropagation", "O(n) Time Complexity").
2.  **chapter**: A grouping of concepts (e.g., "Neural Networks").
3.  **subject**: A broad domain (e.g., "Machine Learning").
4.  **document**: Represents a physical uploaded file.
5.  **note**: Represents a user-created markdown note.
6.  **quiz**: Represents an assessment event.

## 4. Complete Node Schema (JSON)
```json
{
  "id": "uuid4",
  "label": "Dynamic Programming",
  "type": "concept",
  "profile_id": "uuid4",
  "description": "A method for solving complex problems by breaking them down into simpler subproblems.",
  "mastery_score": 0.75,
  "mention_count": 12,
  "first_seen": "2026-06-13T10:00:00Z",
  "last_seen": "2026-06-15T14:30:00Z",
  "roadmap_node_id": "uuid4_or_null",
  "document_ids": ["uuid-doc-1"],
  "chat_session_ids": ["uuid-chat-1", "uuid-chat-2"]
}
```
*   `mastery_score`: (0.0 to 1.0) Driven by quiz results and roadmap completion.
*   `mention_count`: Increments every time the concept is detected in a chat or document.

## 5. Edge Types
Edges are directed (`source` -> `target`).
1.  **prerequisite_of**: Concept A must be learned before Concept B.
2.  **related_to**: Bidirectional (represented as two edges) thematic relation.
3.  **taught_in**: Concept A is taught in Document B or Chapter C.
4.  **referenced_by**: Concept A is mentioned in Note B or Chat C.
5.  **learned_from**: User acquired mastery of Concept A from Document B.
6.  **tested_by**: Concept A is evaluated by Quiz B.

## 6. Complete Edge Schema (JSON)
```json
{
  "source": "uuid_node_a",
  "target": "uuid_node_b",
  "type": "prerequisite_of",
  "weight": 1.0,
  "created_at": "2026-06-13T10:00:00Z"
}
```

## 7. Graph Storage
The graph is serialized to a local JSON file at `~/.atlas/data/graph/knowledge_graph.json`.
It uses the `NetworkX` `node_link_data()` format for easy serialization.
**Atomic Writes**: To prevent corruption, the graph is saved to a temporary file (`graph.tmp.json`) and then atomically renamed to `knowledge_graph.json`.

## 8. In-Memory Graph
At startup (`lifespan.py`), the JSON file is loaded into a `networkx.DiGraph` object in memory.
This in-memory graph is authoritative during runtime. All graph algorithms (shortest path, BFS) run extremely fast in-memory. Writes update the NetworkX object and trigger an asynchronous flush to the JSON file.

## 9. Graph Enrichment Process
The graph grows autonomously via three triggers:
1.  **Document Indexed**: When a PDF is chunked, `graph_enricher` scans the text and extracts key concepts, linking them to the document node (`taught_in`).
2.  **Chat Turn Completed**: The LLM analyzes the chat, detects mentions of existing concepts (increments `mention_count`, updates `last_seen`), or extracts new concepts.
3.  **Quiz Completed**: `mastery_score` is directly updated based on quiz performance.

## 10. Graph Enricher (`graph_enricher.py`)
An AI-powered module using Information Extraction prompts.
**Prompt Concept**: *"Given this text, identify the top 5 technical concepts. For each, provide a label, a short description, and any prerequisite relationships between them. Output JSON."*
Batch processing is used to avoid overwhelming the LLM. It processes documents section by section.

## 11. Graph Query Functions (`graph_query.py`)
Encapsulates NetworkX algorithms:
*   `get_prerequisites(node_id)`: Uses `nx.bfs_edges` traversing `prerequisite_of` edges backwards.
*   `get_related(node_id, depth=2)`: Uses `nx.ego_graph` to get a local neighborhood.
*   `get_concept_path(from_id, to_id)`: Uses `nx.shortest_path` to find a learning route between two concepts.
*   `find_nodes_by_label(query)`: Uses simple string matching or fuzzy matching.
*   `get_weak_concepts(profile_id)`: Filters nodes where `mastery_score < 0.5`.
*   `get_subgraph(node_ids)`: Extracts a sub-graph containing the requested nodes and the edges between them.

## 12. Graph Service (`graph_service.py`)
The business logic wrapper exposed to routers.
*   `add_concept(label, description)`
*   `link_concepts(source_id, target_id, relation_type)`
*   `update_mastery(node_id, score)`
*   `get_full_graph()`

## 13. Graph Store (`graph_store.py`)
Handles the low-level IO.
*   `load_graph()`: Reads JSON, builds DiGraph.
*   `save_graph()`: Writes DiGraph to JSON atomically.
*   Includes a write-lock (`asyncio.Lock`) to prevent concurrent saves from corrupting the file.

## 14. Visualization Architecture
*   **Backend**: `GET /api/v1/graph` returns the `node_link_data` JSON.
*   **Frontend**: `GraphPage.tsx` uses `D3.js` `forceSimulation` (forceManyBody, forceLink, forceCenter).
*   **WebWorker**: The D3 simulation runs in a WebWorker to prevent the React UI thread from freezing when rendering 1000+ nodes.

## 15. Rendering Strategy
*   **Progressive Loading**: Initial view clusters minor nodes. Zooming in reveals them.
*   **Level of Detail (LOD)**: Text labels only render when zoomed in or hovering over a node.

## 16. Node Visual Encoding
*   **Color**: Determined by `type` (e.g., Blue for concepts, Orange for documents).
*   **Border Thickness**: Proportional to `mastery_score` (thick green border = mastered).
*   **Radius**: Proportional to `mention_count` (frequently discussed topics are larger).
*   **Glow**: Nodes with `mastery_score < 0.4` emit a subtle red glow, highlighting weaknesses.

## 17. Edge Visual Encoding
*   `prerequisite_of`: Solid thick line with a directional arrow.
*   `related_to`: Dashed line, no arrows.
*   `taught_in`: Dotted line connecting concept to document.

## 18. User Interactions
*   **Click**: Selects node, opens Context Panel showing description, mastery, and related documents.
*   **Double-Click**: Zooms and centers on the node.
*   **Drag**: Pins a node to a specific coordinate on the canvas.
*   **Search Bar**: Auto-completes concept names, pans camera to the selected node.

## 19. Filter Panel
A UI overlay allowing the user to declutter the graph:
*   Toggle node types (e.g., "Hide Documents").
*   Filter by mastery (e.g., "Show only Weaknesses").
*   Isolate Subgraph: "Show only nodes connected to X".

## 20. Graph API Endpoints
*   `GET /api/v1/profiles/{pid}/graph`: Returns full graph.
*   `PATCH /api/v1/profiles/{pid}/graph/nodes/{id}`: Manual override of node properties.
*   `GET /api/v1/profiles/{pid}/graph/search?q=query`: Search endpoint.

## 21. Performance
NetworkX handles up to ~10,000 nodes and 50,000 edges trivially in Python memory.
*   **Warning Threshold**: System logs a warning if node count exceeds 3,000.
*   **Phase 3 Migration**: If graphs become too large for in-memory NetworkX and D3, the architecture is designed to allow hot-swapping NetworkX for `KuzuDB` (an embedded graph database) without changing the `GraphService` API contracts.

## 22. Graph and Roadmap Integration
The Knowledge Graph is non-linear; the Roadmap is linear.
When a Roadmap node (e.g., "Learn Variables") is marked 'completed', the `RoadmapService` fires an event. The `GraphService` catches this, finds the corresponding graph concept node (via `roadmap_node_id` or label matching), and sets its `mastery_score` to 1.0.

## 23. Graph Export
The JSON graph file is included as-is in the Profile Export ZIP.

## 24. Implementation Sequence
1.  `graph_store.py` (JSON loading/saving).
2.  `graph_query.py` (NetworkX traversal algorithms).
3.  `graph_enricher.py` (LLM extraction prompt).
4.  `graph_service.py` (Business logic layer).
5.  FastAPI Router (`graph.py`).
6.  Background Task Integration (triggering enricher).
7.  Frontend D3 Visualization (`GraphPage.tsx`).

## 25. Master Plan Implementation Addendum

### Normalization and Merge Rules
Graph enrichment must merge concepts instead of creating duplicates.
*   Normalize labels by trimming whitespace, lowercasing for comparison, collapsing punctuation, and singularizing only when obvious.
*   Prefer existing nodes with matching `roadmap_node_id`.
*   Next prefer exact normalized label match inside the same profile.
*   Next use semantic match from `global_graph_nodes` or profile graph embeddings if similarity is above `0.88`.
*   If none match, create a new concept node.
*   Edge uniqueness is `(source, target, type)`. Repeated evidence increases `weight` instead of duplicating the edge.

### Graph Response Shape
`GET /api/v1/profiles/{pid}/graph` should return:
```json
{
  "nodes": [
    {
      "id": "uuid",
      "label": "Dynamic Programming",
      "type": "concept",
      "description": "Solving problems by combining overlapping subproblems.",
      "mastery_score": 0.75,
      "mention_count": 12,
      "roadmap_node_id": "uuid-or-null",
      "document_ids": ["uuid"],
      "chat_session_ids": ["uuid"]
    }
  ],
  "edges": [
    {
      "source": "uuid",
      "target": "uuid",
      "type": "prerequisite_of",
      "weight": 1.0
    }
  ],
  "meta": {
    "node_count": 1,
    "edge_count": 1,
    "generated_at": "2026-06-13T10:00:00Z"
  }
}
```

### Enrichment Prompt Contract
The LLM prompt in `graph_enricher.py` must require strict JSON with two top-level arrays:
```json
{
  "nodes": [
    {
      "label": "Recursion",
      "type": "concept",
      "description": "A function calling itself on smaller inputs."
    }
  ],
  "edges": [
    {
      "source_label": "Base Case",
      "target_label": "Recursion",
      "type": "prerequisite_of",
      "confidence": 0.9
    }
  ]
}
```

Invalid JSON, unsupported edge types, or edges referencing unknown labels should be logged and skipped without failing the parent chat/document task.

### Roadmap and Quiz Integration
*   Roadmap generation should create or link graph nodes for subjects, chapters, and topics.
*   Completing a roadmap node sets the linked graph node mastery to at least `0.8`; formal assessment can raise/lower it afterward.
*   Quiz completion updates graph mastery using the same score used for roadmap mastery.
*   If a graph concept is marked weak (`mastery_score < 0.4`), the dashboard and roadmap context panel should be able to surface it.

### Graph Persistence Requirements
*   Save JSON with atomic temp-file replacement.
*   Keep profile data separable. Either one graph file with `profile_id` on every node, or one file per profile; choose one before implementation and keep API behavior stable.
*   Create automatic backups with the normal backup task.
*   On graph load failure, move the corrupt file to `knowledge_graph.corrupt.{timestamp}.json` and initialize an empty graph rather than crashing permanently.

### Tests Required
*   Same concept mentioned twice merges into one node.
*   Same edge inserted twice increases weight or evidence count only.
*   Subgraph query respects requested depth.
*   Roadmap completion updates linked graph mastery.
*   Corrupt graph JSON is quarantined and a new graph is created.
