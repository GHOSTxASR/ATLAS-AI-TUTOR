# 11. Roadmap Engine

## 1. Roadmap Engine Overview
The Roadmap Engine creates structured, visual learning paths. It acts as the "curriculum" for the AI Tutor. Instead of free-form chatting, the user follows a predefined or AI-generated path of nodes (topics). The active node dictates the context for the AI Tutor.

## 2. Three Roadmap Modes

### Strict Mode
*   **Input**: A Syllabus document (PDF/DOCX) processed by `syllabus_parser.py`.
*   **Process**: The engine performs a direct 1:1 mapping of the syllabus hierarchy to roadmap nodes.
*   **Rule**: The AI is strictly forbidden from adding, removing, or reordering topics. It may only generate short descriptions for each node.
*   **Output**: A rigid hierarchy (Subject → Chapter → Topic).

### Adaptive Mode
*   **Input**: A plain list of topics (from a parsed syllabus) OR a user-provided goal string (e.g., "Teach me Python").
*   **AI Prompt**: The LLM is asked to organize the concepts into the most logically optimal learning sequence, strictly defining prerequisite relationships.
*   **Process**: The engine parses the JSON response to construct a Directed Acyclic Graph (DAG).
*   **Output**: A highly personalized learning sequence optimized for prerequisite scaffolding. Nodes are marked `ai_generated=True`.

### Hybrid Mode
*   **Input**: The Strict Mode structure (the original syllabus) + Adaptive overlay.
*   **Process**: The engine preserves the exact structure of the syllabus but asks the AI to analyze it for missing prerequisites.
*   **Bridge Nodes**: If the syllabus jumps from "Addition" to "Calculus", the AI inserts intermediate "Bridge Nodes" (e.g., "Algebra") as prerequisites, without altering the original syllabus nodes.
*   **Output**: An enhanced syllabus graph with AI scaffolding.

## 3. Roadmap Data Model
*   **`roadmaps`**: Contains `id`, `profile_id`, `title`, `mode`.
*   **`roadmap_nodes`**: The topics. Contains `id`, `node_type`, `status`, `mastery_score`, `parent_id`.
*   **`roadmap_edges`**: The relationships. Contains `source_id`, `target_id`, `edge_type`.

## 4. Node Types
Visually differentiated in the UI:
*   `subject`: Top-level domain (e.g., "Computer Science").
*   `chapter`: Major grouping (e.g., "Data Structures").
*   `topic`: Specific learning item (e.g., "Linked Lists"). The AI Tutor actively teaches at this level.
*   `prerequisite`: A topic required before another.
*   `bridge`: An AI-inserted node in Hybrid mode.

## 5. Node State Machine
A node's `status` drives the learning journey:
*   `not_started`: Default state. Locked if prerequisites exist and are not completed.
*   `not_started` → `in_progress`: Triggered when the user actively selects the node in the UI and starts a chat.
*   `in_progress` → `completed`: Triggered by passing an Assessment, or manually marked by the user.
*   `not_started` → `skipped`: User manually bypasses the node.
*   `in_progress` → `flagged`: User marks the node as needing help/attention.

## 6. Node Attributes
*   `order_index`: Integer for sorting nodes linearly within a chapter.
*   `mastery_score`: (0.0 - 1.0) Driven by quiz results.
*   `time_spent_minutes`: Summed from analytics events.
*   `completed_at`: Timestamp.
*   `metadata_json`: Extensible field for frontend UI properties (e.g., x/y coordinates for ReactFlow).

## 7. Edge Types
*   `prerequisite`: Source must be `completed` or `skipped` before Target can transition from `not_started`.
*   `sequential`: Soft suggestion of order, but doesn't lock the Target.
*   `optional`: Recommended but not required reading.

## 8. Unlock Logic
Evaluated continuously on the frontend and backend.
When a node `status` changes to `completed`, the `RoadmapService` performs a Breadth-First Search (BFS) traversal on outgoing `prerequisite` edges. It checks the target nodes; if *all* incoming prerequisite edges for a target node come from completed nodes, that target node becomes "unlocked" (visually enabled in the UI).

## 9. Roadmap Generation Flow
1.  **User Trigger**: POST `/api/v1/profiles/{pid}/roadmaps` with `document_id` and `mode`.
2.  **Parsing**: `syllabus_parser.py` extracts text from the document.
3.  **LLM Call**: Specific prompt template based on `mode` is sent to the Model Abstraction Layer.
4.  **JSON Validation**: The response is validated against Pydantic schemas. If malformed, retry x2.
5.  **DB Insertion**: `RoadmapRepo` bulk inserts the Roadmap, Nodes, and Edges in a single transaction.
6.  **Return**: Returns the full DAG to the frontend.

## 10. Roadmap Version Control
Syllabuses change. If a user uploads a new version:
1.  The old roadmap is marked as `archived`.
2.  A new roadmap is generated.
3.  **Progress Migration**: The system attempts to match nodes by `title`. If "Linked Lists" is completed in v1, it automatically marks it completed in v2.
4.  **UI**: User is presented with a "Diff" screen showing what was added/removed before accepting the migration.

## 11. Progress Computation
*   **Node Level**: `mastery_score` is an average of the last 3 quiz attempts on that topic.
*   **Parent Level (Chapter/Subject)**:
    *   `Completion %` = `(completed_children / total_children) * 100`.
    *   `Mastery` = Weighted average of children's mastery scores.
*   Computed dynamically via `RoadmapService.compute_progress()`.

## 12. Syllabus Parsing Integration
The `syllabus_parser.py` pipeline uses AI to turn unstructured PDF text into a JSON tree.
If the AI fails to parse the document, fallback logic uses regex to detect common numbering schemes (e.g., "1.", "1.1", "Week 1", "Module A") to build a crude hierarchy.

## 13. Roadmap Service (`roadmap_service.py`)
*   `generate_roadmap(profile_id, document_id, mode)`: Core generation logic.
*   `get_active_roadmap(profile_id)`: Fetches the unarchived roadmap DAG.
*   `update_node_status(node_id, status)`: Transitions state, updates `completed_at`, triggers graph updates.
*   `get_next_node(profile_id)`: Algorithmically recommends the next `not_started` unlocked node.
*   `compute_progress(roadmap_id)`: Returns aggregation stats.
*   `regenerate(roadmap_id)`: Re-runs the Adaptive/Hybrid AI phase if the user dislikes the output.
*   `archive(roadmap_id)`: Soft-deletes.

## 14. Roadmap Repository (`roadmap_repo.py`)
Handles SQLAlchemy ORM models. Includes a method to fetch the entire DAG (Roadmap + all Nodes + all Edges) efficiently using `joinedload`.

## 15. Roadmap Context in Tutor
The active roadmap node severely restricts the AI Tutor.
*   The `TutorOrchestrator` fetches the active node via `get_active_roadmap`.
*   It injects into the prompt: `"Current Topic: {node.title}. Do not explain concepts outside this scope unless explicitly asked."`
*   **Transition Detection**: If the user asks about the next topic, the AI is prompted to suggest: "It looks like you're asking about X. Should we mark the current topic complete and move on?"

## 16. Roadmap Visualization
Frontend uses **ReactFlow** for the DAG view.
*   Nodes are custom React components (Cards) displaying the title, description, and status icon.
*   Colors: Green (completed), Blue (in_progress), Gray (not_started/locked).
*   Mastery indicator: A small progress bar inside the node card.
*   List View: A toggleable alternative view for users who prefer standard hierarchical outlines instead of node graphs.

## 17. Roadmap UI Controls
*   **Mode Selector**: Radio buttons for Strict/Adaptive/Hybrid during creation.
*   **Regenerate Button**: "I don't like this path, try again."
*   **Node Detail Panel**: Right-side panel opening on node click. Shows full description, linked documents, and Action buttons (Mark Complete, Skip, Flag).

## 18. Adaptive Reordering
In Adaptive Mode, the roadmap is dynamic.
If a user repeatedly fails a quiz on a node, the system uses the Memory System's `weakness` records to detect missing foundational knowledge. It then prompts the LLM to insert a new `bridge` prerequisite node directly in front of the failed node, dynamically altering the DAG mid-journey.

## 19. Roadmap API Endpoints
*   `GET /api/v1/profiles/{pid}/roadmaps`: Returns lists of available roadmaps.
*   `POST /api/v1/profiles/{pid}/roadmaps`: Creates new.
*   `GET /api/v1/profiles/{pid}/roadmaps/{id}`: Returns the full DAG JSON.
*   `PATCH /api/v1/profiles/{pid}/roadmaps/{id}/nodes/{nid}`: `{"status": "completed"}`.

## 20. Implementation Sequence
1.  `syllabus_parser.py` (Text to JSON).
2.  `roadmap_repo.py` (SQLAlchemy models and queries).
3.  `roadmap_service.py` (Strict mode implementation first).
4.  `routers/roadmap.py` (API endpoints).
5.  Frontend List View (Basic rendering).
6.  `roadmap_service.py` (Adaptive and Hybrid modes via AI).
7.  Frontend ReactFlow View (DAG rendering).

## 21. Master Plan Completion Addendum

### Syllabus Parser Output Contract
`syllabus_parser.py` must normalize every input into this shape:
```json
{
  "title": "GATE CSE Syllabus",
  "subjects": [
    {
      "title": "Programming",
      "chapters": [
        {
          "title": "Data Structures",
          "topics": [
            {
              "title": "Linked Lists",
              "description": "Singly and doubly linked lists",
              "order_index": 1
            }
          ]
        }
      ]
    }
  ],
  "warnings": []
}
```

The parser may use AI, layout cues, numbering patterns, and headings, but it must output deterministic JSON validated by Pydantic.

### Strict Mode Rules
*   Preserve syllabus order and hierarchy exactly.
*   Do not add bridge/prerequisite nodes.
*   AI may add descriptions only when missing.
*   Edges should be `sequential` unless the syllabus explicitly names prerequisites.
*   This is the MVP roadmap mode and should be built first.

### Adaptive Mode Rules
*   Accept either parsed syllabus topics or a user goal string.
*   Ask the model for prerequisite ordering and a DAG.
*   Validate that the graph is acyclic before saving.
*   If a cycle is detected, request one repair from the model; if still cyclic, break the lowest-confidence edge and log a warning.
*   Mark AI-added nodes with `ai_generated = true`.

### Hybrid Mode Rules
*   Preserve every original syllabus node and parent-child relation.
*   Allow AI to insert `bridge` nodes only as prerequisites.
*   Bridge nodes must be visually marked in the UI.
*   User must be able to hide bridge nodes in the roadmap view without deleting them.

### Regeneration and Progress Migration
Regeneration must not erase user progress.
1. Archive the old roadmap.
2. Generate the new roadmap as version `old.version + 1`.
3. Match old and new nodes by normalized title, parent title, and type.
4. Copy `status`, `mastery_score`, `time_spent_minutes`, and `completed_at` for confident matches.
5. Present a diff summary to the frontend: added nodes, removed nodes, migrated nodes, uncertain matches.

### Unlock and Status Validation
*   A node can become `in_progress` only if all hard prerequisite incoming edges are completed or skipped.
*   `completed` should require either manual user action or a passing assessment, depending on profile settings.
*   `flagged` does not block downstream progress by itself.
*   `skipped` unlocks dependents but records an analytics event and may lower confidence in mastery.

### Tests Required
*   Strict mode preserves input order.
*   Adaptive mode rejects or repairs cycles.
*   Hybrid mode inserts bridge nodes without reparenting original syllabus nodes.
*   Completing prerequisites unlocks the next node.
*   Regeneration migrates progress for matching nodes and archives the prior roadmap.
