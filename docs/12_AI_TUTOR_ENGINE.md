# 12. AI Tutor Engine

## 1. AI Tutor Overview
The AI Tutor Engine is the core intelligence of Atlas. It is not a standard pass-through chatbot. It is a highly orchestrated system that utilizes persistent memory, multi-source RAG, roadmap context, and formal assessments to simulate a personalized human tutor.

## 2. Tutor Orchestrator (`tutor_orchestrator.py`)
The central "brain" responsible for every chat turn.
**Responsibilities**:
1. Intercept incoming user messages.
2. Gather all context (Profile, Roadmap, Memory, RAG, History).
3. Construct the prompt based on the active Learning Mode.
4. Manage token budgets to prevent overflow.
5. Stream the response via the Model Abstraction Layer.
6. Trigger post-turn tasks (memory extraction, graph updates).

## 3. Full Context Assembly Flow
When a user sends a message, the Orchestrator executes this step-by-step pipeline:
1.  **Load ProfileContext**: `ProfileService.get_profile(id)`.
2.  **Get Roadmap Context**: `RoadmapService.get_active_node()`.
3.  **Retrieve Memory**: Embed the message, query `MemoryService` for top-5 semantic matches + all weaknesses related to the active roadmap node.
4.  **Retrieve RAG Context**: Call `RAGService.retrieve()` to get the top 8 document/note chunks.
5.  **Get History**: Fetch the last 20 messages from `ChatService` (sliding window).
6.  **Select Prompt**: Choose the template matching the current `ChatMode`.
7.  **Assemble Prompt**: Inject Context 1-5 into the Prompt Template. Calculate tokens. Truncate history/RAG if budget exceeded.
8.  **Call LLM**: `ModelAbstractionLayer.chat_complete(stream=True)`.
9.  **Pipe Stream**: Yield tokens to the `ws_chat.py` WebSocket router.
10. **Finalize**: On stream end, save the full assistant message to SQLite, fire `citations` event, and dispatch APScheduler tasks for Memory and Graph enrichment.

## 4. Learning Modes
The user can switch the Tutor's behavior on the fly:
*   **Deep Learning**: The default. Focuses on thorough, ground-up explanations using analogies and step-by-step logic.
*   **Revision**: Fast-paced, concise. Summarizes key points without long explanations.
*   **Summary**: "TL;DR" mode. Distills the current roadmap node into 3 bullet points.
*   **General Knowledge**: Bypasses the Roadmap restrictions. Allows the user to ask anything outside the curriculum.
*   **Quiz**: Interactive Socratic mode. The tutor asks a question, waits for the user's answer, and provides hints rather than direct answers.
*   **Assessment**: Formal, non-interactive mode. Generates a multi-part question, waits for a full answer, and scores it 0-100.

## 5. Tutor Persona
Defined by a foundational system prompt injected into every request:
*"You are the Atlas AI Tutor. Your name is {TutorName}. Your goal is to guide the user to mastery of the subject, not just give them the answers. Employ the Socratic method when appropriate. Do not be overly verbose. Never be condescending. You are currently teaching {ActiveNode}. Treat the user according to their known profile: {MemoryContext}."*

## 6. Token Budget Management
To prevent `context_length_exceeded` errors and manage costs.
Assuming a 128K context window:
*   System Prompt + Persona: 1K max
*   Memory Context: 2K max
*   RAG Context: 8K max
*   Chat History: 6K max
*   Response Buffer: 4K max
*   Total target budget per request: ~21K tokens.
If the budget exceeds limits (e.g., using a smaller local model with 8K context), truncation occurs in this order:
1.  Oldest chat history messages.
2.  Lowest-ranked RAG chunks.
3.  Low-confidence Memory records.

## 7. Context Window Sliding
Chat history is aggressively managed.
*   Starts by including the last 20 messages.
*   If token limits approach, drops to 10, then 5.
*   Always preserves the absolute last 2 messages (immediate context) and the first message of the session (topic setter).

## 8. Topic Transition Logic
The Tutor is aware of the Roadmap.
If the active node is "Variables" and the user asks "What is a function?", the Orchestrator detects the transition.
It injects a prompt instruction: *"The user is asking about a topic outside the current node. Briefly explain it, but guide them back to the current node, or ask if they want to formally complete the current node and move forward in the roadmap."*

## 9. Model Abstraction Layer (`models/abstraction.py`)
An interface pattern isolating the application from specific AI provider APIs.
Defines `BaseModelClient` with abstract methods:
*   `async chat_complete(messages: list, stream: bool, kwargs)`
*   `async embed(text: str)`
*   `count_tokens(text: str) -> int`
*   `get_model_info() -> dict`

## 10. OpenAI Client (`openai_client.py`)
Implements `BaseModelClient` using `openai` (AsyncOpenAI).
*   Handles `gpt-4o`, `gpt-4-turbo`, `gpt-3.5-turbo`.
*   Uses `tiktoken` for exact token counting.
*   Yields chunks from the async generator for streaming.

## 11. Anthropic Client (`anthropic_client.py`)
Implements `BaseModelClient` using `anthropic` (AsyncAnthropic).
*   Handles `claude-3-5-sonnet`, `claude-3-opus`.
*   Converts OpenAI-style message arrays (system/user/assistant) into Anthropic's specific format (system param + user/assistant array).

## 12. Ollama Client (`ollama_client.py`)
Implements `BaseModelClient` using `httpx.AsyncClient` calling `localhost:11434`.
*   Supports any installed local model (e.g., `llama3`, `mistral`, `phi3`).
*   Uses basic length-based approximation for token counting since `tiktoken` doesn't strictly apply.

## 13. Provider Factory
`get_model_client(settings: Settings)` dependency injects the correct client based on the user's `settings.toml`. Allows hot-swapping providers without restarting the server.

## 14. Fallback Chain
If the primary provider (e.g., OpenAI) returns a 5xx error or times out:
1.  Retry 3 times with exponential backoff (1s, 2s, 4s).
2.  If it still fails, and a fallback provider is configured (e.g., Ollama), automatically switch to the fallback provider for that specific request.
3.  If all fail, raise `ModelError`, which the WebSocket transmits as a graceful error message to the user.

## 15. Streaming Protocol
`TutorOrchestrator` returns an `AsyncGenerator[str]`.
`ws_chat.py` iterates this generator:
```python
async for token in orchestrator.handle_chat_turn(...):
    await websocket.send_json({"type": "token", "content": token})
await websocket.send_json({"type": "done", "citations": citation_data})
```

## 16. Cost Tracking
After every generation, `analytics_events` records:
*   Provider/Model used.
*   Prompt tokens.
*   Completion tokens.
*   Estimated cost (based on hardcoded $ per 1M token rates).
Displayed in the Settings UI.

## 17. Chat System Design
*   **Sessions**: Grouping of messages. `ChatSession` table.
*   **Messages**: Individual turns. `ChatMessage` table.
*   Users can create a session per topic or use one mega-session (sliding window handles context limits).

## 18. Chat Session Management
When a new session starts, after the first Assistant reply, a background task sends the first User message and Assistant reply to an LLM: *"Generate a 3-5 word title for this conversation."* Updates the session title asynchronously.

## 19. Message Storage
*   User message saved to SQLite immediately upon receipt.
*   Assistant message is NOT saved while streaming to avoid DB hammering.
*   Upon `done`, the full string is saved.
*   If the WebSocket disconnects mid-stream, the partial message is saved with `status="incomplete"`.

## 20. WebSocket Connection
*   `ws://localhost:8000/ws/chat/{session_id}`
*   Frontend reconnects automatically with exponential backoff if dropped.
*   Ping/Pong frames keep the connection alive.

## 21. Assessment Mode
A distinct flow within `TutorOrchestrator`.
1.  User enters Assessment Mode.
2.  Tutor generates a 3-part essay/coding question based on the active node.
3.  User replies.
4.  Tutor evaluates the reply against a rubric hidden in the system prompt.
5.  Tutor outputs a JSON score `{"score": 85, "feedback": "..."}`.
6.  `AssessmentService` catches the JSON, updates `RoadmapNode.mastery_score`, and updates the Graph.

## 22. Quiz Mode
Similar to Assessment, but lower stakes. It's an interactive back-and-forth. The LLM is prompted to ask Multiple Choice or short-answer questions, providing immediate feedback on each turn.

## 23. Post-Turn Async Jobs
The isolation of background tasks is critical.
When the AI finishes responding, `memory_extraction_task` and `graph_enrichment_task` are pushed to APScheduler. If they crash or the LLM hallucinates during extraction, the user's chat experience is completely unaffected.

## 24. Model Configuration
Stored in `settings.toml`:
```toml
[models]
provider = "openai" # openai, anthropic, ollama
model_name = "gpt-4o"
temperature = 0.7
max_tokens = 1024
```
Adjustable via the Frontend Settings page.

## 25. Implementation Sequence
1.  `models/abstraction.py` & specific provider clients.
2.  `chat_repo.py` and `chat_service.py` (CRUD for sessions/messages).
3.  `tutor_orchestrator.py` (Basic echoing first, then prompt injection).
4.  `routers/ws_chat.py` (WebSocket integration).
5.  Context injections (Memory, Roadmap, RAG).
6.  Implement specific Learning Modes.
7.  Fallback chain and error handling.

## 26. Master Plan Completion Addendum

### Orchestrator Input Contract
`handle_chat_turn()` should accept a structured object, not loose parameters:
```json
{
  "profile_id": "uuid",
  "session_id": "uuid",
  "user_message_id": "uuid",
  "content": "Explain recursion.",
  "mode": "deep",
  "roadmap_node_id": "uuid-or-null",
  "document_ids": [],
  "stream": true
}
```

The orchestrator should return an async stream of structured events internally; the WebSocket router serializes them for the client.

### Context Assembly Order
Build the prompt in this order:
1. System persona and safety/local-first rules.
2. Learning mode instructions.
3. Active profile and learning preferences.
4. Active roadmap node and transition policy.
5. Relevant memory records.
6. RAG context with citation IDs.
7. Recent chat history.
8. Current user message.

Token trimming must happen after all blocks are built, using the priority rules in Section 6.

### Mode-Specific Behavior
| Mode | Required Behavior |
| :--- | :--- |
| `deep` | Teach step by step, include examples, cite documents when used, ask a short check question when appropriate. |
| `revision` | Short, high-density review; prioritize bullet summaries and common mistakes. |
| `summary` | Summarize the active topic or selected document; avoid introducing unrelated concepts. |
| `general` | Allow off-roadmap questions while still using profile preferences and memory. |
| `quiz` | Ask one question at a time, wait for answer, give hints before final answer. |
| `assessment` | Generate formal prompt, evaluate with rubric, return score and feedback parsable by `QuizService`. |

### Provider Interface Requirements
Every provider client must implement:
*   `chat_complete(messages, stream, **kwargs)`
*   `embed(texts)` for batch embeddings where supported.
*   `count_tokens(text)` with provider-specific tokenizer or documented approximation.
*   `get_model_info()` returning context window, supports streaming, supports embeddings, and pricing metadata if known.

### Streaming Persistence Rules
*   Save the user message before calling the model.
*   Accumulate assistant tokens in memory while streaming.
*   Save the assistant message once on `done`.
*   On disconnect, try to cancel the provider stream and save partial content with `status = incomplete`.
*   Store `retrieved_chunks`, `memory_ids_used`, `graph_nodes_mentioned`, `model_used`, `token_count`, and `latency_ms` on the assistant message.

### Post-Turn Task Dispatch
After assistant persistence:
1. Record analytics event for model usage and latency.
2. Dispatch memory extraction with session/message IDs.
3. Dispatch graph enrichment with the final assistant and user message.
4. If quiz/assessment mode completed, dispatch mastery updates through `QuizService` and `RoadmapService`.

These jobs must be best-effort and must not change the already-returned chat answer.

### Tests Required
*   Prompt assembly includes roadmap, memory, RAG, and history in the expected order.
*   Token trimming preserves the latest user message and system prompt.
*   Provider failure emits `MODEL_UNAVAILABLE`.
*   WebSocket disconnect saves an incomplete assistant message.
*   Assessment mode returns parseable score data and updates mastery through service calls.
