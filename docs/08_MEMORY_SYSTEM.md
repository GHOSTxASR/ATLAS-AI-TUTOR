# 08. Memory System

## 1. Memory System Philosophy
The core differentiator of Atlas is **Persistent Intelligence**. A standard chatbot forgets the user between sessions. Atlas "remembers" the learner. The Memory System is responsible for extracting, storing, and seamlessly injecting facts, struggles, and preferences into the AI's context window, allowing the Tutor to adapt its teaching style and reference past interactions.

## 2. Memory Categories
Every memory record is classified into one of 7 categories:
1.  **strength**: Topics or skills the user has demonstrated a solid understanding of. (e.g., "Understands for-loops well.")
2.  **weakness**: Areas where the user struggles or makes repeated mistakes. (e.g., "Confuses pass-by-value with pass-by-reference.")
3.  **completed**: Major milestones or roadmap nodes the user has finished. (e.g., "Completed Chapter 1: Introduction.")
4.  **preference**: How the user likes to learn. (e.g., "Prefers visual analogies over mathematical formulas.")
5.  **assessment**: Results from formal quizzes. (e.g., "Scored 80% on Recursion quiz.")
6.  **fact**: Factual statements the user made about themselves. (e.g., "Is preparing for a software engineering interview.")
7.  **context**: Situational data regarding the current learning environment.

## 3. Memory Record Schema
Stored in SQLite `memory_records`:
| Column | Type | Constraints | Example |
| :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | `uuid4` |
| `profile_id` | TEXT | FK(profiles.id) | `uuid4` |
| `category` | TEXT | NOT NULL | "weakness" |
| `content` | TEXT | NOT NULL | "Struggles to identify base cases." |
| `confidence` | REAL | 0.0 - 1.0 | 0.85 |
| `created_at` | TEXT | ISO 8601 | `2026-06-13T10:00:00Z` |

*Note: Embeddings of the `content` are stored in ChromaDB under `{profile_id}_memory`.*

## 4. Memory Extraction Pipeline
**Trigger**: Runs asynchronously via APScheduler (`memory_extraction_task.py`) immediately after a chat turn completes.
**Process**:
1.  Extract the last N messages (User + Assistant).
2.  Send to an LLM with a specific Extraction Prompt:
    *"Analyze the following conversation. Identify any new strengths, weaknesses, preferences, or facts about the user. Return a JSON array of objects: { "category": "...", "content": "..." }. If nothing new, return an empty array."*
3.  Parse the JSON response.
4.  **Deduplication**: For each extracted memory, embed the `content` and query ChromaDB. If cosine similarity > 0.85 to an existing memory, update the existing memory's confidence score instead of inserting a duplicate.
5.  If new, insert into SQLite `memory_records`.
6.  Embed the `content` and insert into ChromaDB `{profile_id}_memory`.

## 5. Memory Retrieval at Chat Time
When the user sends a message:
1.  The message (and HyDE expansion) is embedded.
2.  ChromaDB `{profile_id}_memory` is queried for the top 5 most semantically similar memories.
3.  Simultaneously, SQLite is queried for ALL `weakness` and `preference` records related to the current roadmap node/subject.
4.  Results are merged, deduplicated, and formatted into the Context Block:
    ```markdown
    <LEARNER_PROFILE>
    Strengths: Understands basic syntax.
    Weaknesses: Struggles with pointers.
    Preferences: Prefers code examples over theory.
    </LEARNER_PROFILE>
    ```

## 6. Memory Confidence System
Memories are not absolute; they have a `confidence` score (0.0 to 1.0).
*   **Initial Extraction**: Usually assigned 0.5 - 0.7 depending on the clarity of the user's statement.
*   **Reinforcement**: If the extraction pipeline identifies the same weakness again, the confidence of the existing record increases by `0.2` (capped at 1.0).
*   **Contradiction**: If the user demonstrates mastery of a topic previously marked as a weakness, the confidence of the weakness record drops by `0.4`.

## 7. Confidence Decay
Inspired by Spaced Repetition (SuperMemo/SM-2).
*   A weekly APScheduler job runs `decay_old_records()`.
*   Formula: `new_confidence = current_confidence * 0.95` (decays 5% per week if not reinforced).
*   If `confidence < 0.2`, the memory record is automatically deleted from SQLite and ChromaDB to prevent outdated assumptions from polluting the context window.

## 8. Memory Deduplication
Before inserting a new memory, the semantic similarity is checked against existing records in ChromaDB.
Threshold: `0.85` cosine similarity.
If a match is found:
*   The texts are compared via LLM: *"Do these mean the same thing?"*
*   If yes, the confidence is merged/increased.
*   If no, they are kept separate.

## 9. Memory-Informed Tutoring
The AI Tutor's system prompt is heavily influenced by the injected memory.
*   **Weakness-Aware**: If a weakness in "pointers" is in memory, the tutor will proactively explain pointer mechanics when introducing linked lists.
*   **Strength Acknowledgment**: The tutor will skip rudimentary explanations for topics in the `strength` category.
*   **Preference-Respecting**: If the user prefers "Socratic method", the tutor will ask guiding questions rather than giving direct answers.

## 10. Memory UI
*   **Component**: `MemoryPage.tsx`.
*   Displays a datatable of all memories.
*   Filters: By Category, By Confidence threshold.
*   Actions: Users can manually Edit the text, Delete a false memory, or Add a manual entry (e.g., "I already know Python, don't teach me syntax").

## 11. Memory Service API (`memory_service.py`)
*   `extract_memories(session_id: str, messages: list[dict]) -> None`: Triggers async pipeline.
*   `retrieve_relevant(profile_id: str, query: str, limit: int = 5) -> list[MemoryRecord]`: RAG query.
*   `get_all(profile_id: str, filters: dict) -> list[MemoryRecord]`: Used by UI.
*   `create_manual(profile_id: str, record: dict) -> MemoryRecord`: User-created entry.
*   `update(memory_id: str, content: str) -> MemoryRecord`: Inline edit.
*   `delete(memory_id: str) -> None`: Manual deletion.
*   `decay_old_records() -> int`: Scheduled task, returns count of deleted records.

## 12. Memory Background Task
`tasks/memory_extraction_task.py`.
Designed to fail silently. If the LLM extraction times out or returns malformed JSON, the error is logged, but it does not interrupt the user's chat experience.

## 13. Memory and Assessment
When a user completes a formal Quiz, the `AssessmentService` directly creates Memory Records:
*   Score > 85%: Creates a `strength` record for the topic.
*   Score < 50%: Creates a `weakness` record for the topic.
This bypasses the LLM extraction pipeline, creating high-confidence (1.0) ground-truth memories.

## 14. Memory Export
Included in the Profile Export ZIP.
Serialized as a `memories.csv` or `memories.json` file. Useful for backing up learning state or migrating to a different instance.

## 15. Privacy Considerations
Memories contain highly personal assessments of a user's intelligence and learning habits.
*   **Local Only**: Never transmitted to a central server.
*   **User Control**: The UI provides full CRUD access. The user can view and delete everything the system "thinks" about them.
*   **Clear Data**: Deleting a profile wipes the SQLite records and drops the ChromaDB `{profile_id}_memory` collection instantly.

## 16. Implementation Notes for Coding Agents
*   **ChromaDB Collection**: Must strictly adhere to `{profile_id}_memory`.
*   **Embedding Function**: Use the same embedding model configured for documents to ensure vector dimension compatibility.
*   **Metadata**: When inserting to ChromaDB, include `{"memory_id": "uuid"}` to allow easy deletion when a record decays or is manually removed.

## 17. Master Plan Completion Addendum

### Required Memory Fields
The implementation must include the full master-plan memory shape, not only the compact schema above:
*   `subject`: topic/domain the memory applies to, normalized when possible to a roadmap or graph label.
*   `source`: `chat`, `assessment`, or `manual`.
*   `source_id`: session ID, message ID, quiz attempt ID, or manual entry ID.
*   `updated_at`: last reinforcement/edit timestamp.
*   `is_active`: soft delete flag used to exclude records from retrieval.
*   `embedding_id`: vector ID in `{profile_id}_memory`.

### Extraction Prompt Contract
The extraction prompt must require strict JSON:
```json
[
  {
    "category": "weakness",
    "subject": "recursion",
    "content": "The learner struggles to identify base cases.",
    "confidence": 0.72,
    "evidence": "User confused the base case in two examples."
  }
]
```

If the LLM returns prose, invalid JSON, or unsupported categories, the task logs the failure and inserts nothing.

### Confidence Update Rules
| Event | Rule |
| :--- | :--- |
| Same memory reinforced | `min(1.0, confidence + 0.2)` |
| Similar but weaker evidence | `min(1.0, confidence + 0.1)` |
| Direct contradiction | `max(0.0, confidence - 0.4)` |
| User manually edits memory | Set `source = manual`, preserve old source in metadata if needed, and do not auto-delete by decay. |
| Quiz score above 85% | Create or reinforce `strength` with confidence `1.0`. |
| Quiz score below 50% | Create or reinforce `weakness` with confidence `1.0`. |

### Retrieval Rules
*   Retrieve semantic top-k memories from ChromaDB.
*   Always include active high-confidence `preference` records even if semantic similarity is low.
*   Always include active high-confidence weaknesses for the active roadmap node or graph concept.
*   Exclude `is_active = false` records from prompt context and ChromaDB results.
*   Sort final prompt memories by: active topic match, category priority, confidence, recency.

Category priority for chat prompts:
1. `preference`
2. `weakness`
3. `strength`
4. `assessment`
5. `completed`
6. `fact`
7. `context`

### Privacy and User Control Requirements
*   The Memory UI must allow users to view every active memory used by the tutor.
*   Users must be able to delete a memory; deletion removes SQLite active status and deletes the ChromaDB vector.
*   Profile export must include memory content and provenance.
*   Profile deletion must remove memory SQLite rows and drop the profile memory collection.
*   Logs must never include raw memory content unless debug logging is explicitly enabled by a developer.

### Tests Required
*   Duplicate semantic memory reinforces existing record instead of inserting a duplicate.
*   Manual delete removes the ChromaDB vector ID.
*   Retrieval includes preferences even when query similarity is low.
*   Assessment completion creates deterministic high-confidence memories.
*   Malformed LLM extraction output creates no records and does not break chat.
