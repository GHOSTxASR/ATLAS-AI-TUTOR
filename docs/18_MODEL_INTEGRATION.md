# 18. Model Integration

## 1. Purpose
This document defines how Atlas integrates with chat models, embedding models, local providers, streaming APIs, fallback chains, token counting, and cost tracking.

Related documents:
* `07_RAG_ARCHITECTURE.md`: retrieval and context assembly.
* `08_MEMORY_SYSTEM.md`: memory extraction prompts.
* `11_ROADMAP_ENGINE.md`: roadmap generation prompts.
* `12_AI_TUTOR_ENGINE.md`: tutor orchestration.
* `17_SECURITY_AND_PRIVACY.md`: API key and outbound data rules.

## 2. Model Integration Goals
* Keep provider-specific code isolated.
* Support cloud and local model providers.
* Stream chat responses reliably.
* Support batch embeddings.
* Provide deterministic JSON-generation paths for extraction tasks.
* Track token usage and estimated cost.
* Fail gracefully when models are unavailable.

## 3. Provider Abstraction
Create `backend/app/models/abstraction.py`.

Required interface:
```python
class BaseModelClient:
    async def chat_complete(self, messages: list[dict], stream: bool = False, **kwargs):
        ...

    async def embed(self, texts: list[str], **kwargs) -> list[list[float]]:
        ...

    def count_tokens(self, text: str) -> int:
        ...

    def get_model_info(self) -> dict:
        ...
```

`get_model_info()` returns:
```json
{
  "provider": "openai",
  "chat_model": "gpt-4o",
  "embedding_model": "text-embedding-3-small",
  "context_window": 128000,
  "supports_streaming": true,
  "supports_embeddings": true,
  "supports_json_mode": true,
  "input_cost_per_1m": 0.0,
  "output_cost_per_1m": 0.0
}
```

## 4. Provider Factory
Create `backend/app/models/provider_factory.py`.

Responsibilities:
* Read active provider from `Settings`.
* Load/decrypt required API key.
* Instantiate provider client.
* Validate provider supports requested operation.
* Provide fallback provider when configured.

Factory methods:
* `get_chat_client(settings)`
* `get_embedding_client(settings)`
* `get_model_client(settings, purpose)`

Allowed `purpose` values:
* `chat`
* `embedding`
* `hyde`
* `memory_extraction`
* `roadmap_generation`
* `quiz_generation`
* `graph_enrichment`

## 5. Configuration
Canonical settings live in `settings.toml`:
```toml
[model]
provider = "openai"
chat_model = "gpt-4o"
embedding_model = "text-embedding-3-small"
temperature = 0.7
max_tokens = 4096
context_window = 128000

[ollama]
base_url = "http://localhost:11434"
chat_model = "llama3"
embedding_model = "nomic-embed-text"
```

API keys live in encrypted `secrets.enc`, not in TOML.

## 6. OpenAI Client
File: `backend/app/models/openai_client.py`

Responsibilities:
* Use async OpenAI client.
* Stream chat completions.
* Generate embeddings in batches.
* Use provider-supported JSON mode where needed.
* Use `tiktoken` for token counting when available.
* Normalize provider errors to `ModelError` or `ConfigurationError`.

Required supported operations:
* Tutor chat.
* HyDE generation.
* Memory extraction.
* Roadmap generation.
* Quiz generation/scoring.
* Graph enrichment.
* Embeddings.

Error handling:
* 401/403 -> `ConfigurationError`.
* 429 -> retry with backoff, then `ModelError`.
* 5xx/timeouts -> retry with backoff, then fallback if configured.

## 7. Anthropic Client
File: `backend/app/models/anthropic_client.py`

Responsibilities:
* Convert internal OpenAI-style messages to Anthropic message format.
* Handle `system` prompt separately where required.
* Stream response deltas.
* Support JSON-output prompting even when native JSON mode is not available.
* Use approximate token counting if exact tokenizer is unavailable.

Anthropic may not be used for embeddings in MVP unless a supported embedding endpoint is configured. If selected for chat with OpenAI embeddings, document that split-provider setup in settings.

## 8. Ollama Client
File: `backend/app/models/ollama_client.py`

Responsibilities:
* Use `httpx.AsyncClient`.
* Call local Ollama endpoint at `settings.ollama.base_url`.
* Support streaming chat.
* Support local embedding model when available.
* Handle unavailable local daemon with clear settings error.

Default local models:
* Chat: `llama3`
* Embedding: `nomic-embed-text`

Failure behavior:
* If Ollama daemon is not running, return `MODEL_UNAVAILABLE` with instructions to start Ollama.
* Do not fallback from local-only mode to cloud unless the user configured fallback explicitly.

## 9. Embedding Models
Supported embedding options:
| Provider | Model | Dimensions | Notes |
| :--- | :--- | :--- | :--- |
| OpenAI | `text-embedding-3-small` | 1536 | Default. |
| OpenAI | `text-embedding-3-large` | 3072 | Higher quality/cost. |
| SentenceTransformers | `BAAI/bge-small-en-v1.5` | 384 | Offline option. |
| Ollama | `nomic-embed-text` | 768 | Local option. |

Embedding output dimension must be stored in vector metadata and cache records.

When embedding model changes:
1. Detect dimension/model mismatch.
2. Mark affected documents/notes/memories for re-embedding.
3. Clear incompatible ChromaDB collections or create versioned collections.
4. Queue re-embedding.
5. Warn user in Settings before applying.

## 10. Streaming Contract
Provider clients may stream provider-native chunks internally, but must normalize output to text deltas.

Internal stream event shape:
```json
{
  "type": "token",
  "content": "partial text"
}
```

The orchestrator enriches final metadata:
```json
{
  "type": "done",
  "message_id": "uuid",
  "model_used": "gpt-4o",
  "prompt_tokens": 1200,
  "completion_tokens": 300,
  "latency_ms": 1500
}
```

Rules:
* Accumulate full assistant response while streaming.
* Save assistant message once.
* On provider stream failure, emit structured error and persist incomplete status if content exists.

## 11. JSON Output Tasks
Several tasks require strict JSON:
* Memory extraction.
* Roadmap generation.
* Quiz generation.
* Quiz scoring.
* Graph enrichment.

Rules:
* Use native JSON mode if provider supports it.
* Otherwise instruct model to return only JSON.
* Parse with strict JSON parser.
* Validate with Pydantic.
* Retry malformed output at most two times with a repair prompt.
* If still invalid, log and fail the background task or return a structured route error.

## 12. Prompt Families

### Tutor Chat Prompt
Inputs:
* Persona.
* Learning mode.
* Profile preferences.
* Roadmap node.
* Memory context.
* RAG context.
* Chat history.
* User message.

Output:
* Natural language answer.
* Citation markers when document context is used.

### HyDE Prompt
Input:
* User question.
* Active topic.

Output:
* Short hypothetical answer for retrieval only.

Rules:
* Never show HyDE output to user.
* If HyDE fails, use raw expanded query.

### Memory Extraction Prompt
Output JSON:
```json
[
  {
    "category": "weakness",
    "subject": "recursion",
    "content": "The learner struggles with base cases.",
    "confidence": 0.72
  }
]
```

### Roadmap Generation Prompt
Output JSON with nodes and edges:
```json
{
  "nodes": [],
  "edges": []
}
```

Strict mode should preserve source order. Adaptive/hybrid may add prerequisites according to `11_ROADMAP_ENGINE.md`.

### Quiz Prompt
Output JSON:
```json
{
  "questions": [
    {
      "id": "q1",
      "type": "multiple_choice",
      "prompt": "Question text",
      "choices": ["A", "B", "C", "D"],
      "answer": "A",
      "rubric": "Why A is correct"
    }
  ]
}
```

## 13. Token Counting
Use exact tokenizers where practical.

Fallback:
```text
estimated_tokens = ceil(character_count / 4)
```

Token accounting must record:
* prompt tokens.
* completion tokens.
* total tokens.
* model name.
* provider.
* latency.
* estimated cost.

## 14. Fallback Chain
Fallback behavior:
1. Try primary provider.
2. Retry transient errors with exponential backoff: 1s, 2s, 4s.
3. If still failing and fallback provider configured, try fallback once.
4. If fallback fails, raise `ModelError`.

Do not fallback on:
* Invalid API key.
* Missing API key.
* User-selected local-only mode.
* Prompt validation errors.

## 15. Rate Limits and Backoff
Backoff applies to:
* Chat completions.
* Embeddings.
* JSON extraction tasks.

Embedding batch retry:
* Retry whole batch if provider requires.
* If batch repeatedly fails, split batch and retry smaller chunks.
* Mark failed queue rows with retry count and error after max attempts.

## 16. Cost Tracking
After every model call, write an `analytics_events` record:
```json
{
  "event_type": "model_call_completed",
  "entity_type": "model",
  "entity_id": "chat_message_or_task_id",
  "value": 0.00042,
  "metadata_json": {
    "provider": "openai",
    "model": "gpt-4o",
    "prompt_tokens": 1200,
    "completion_tokens": 300,
    "latency_ms": 1500,
    "purpose": "chat"
  }
}
```

If pricing is unknown, store token counts and set cost to null.

## 17. Privacy Rules for Model Calls
Before sending context:
* Filter by active profile.
* Include only selected/retrieved chunks.
* Exclude inactive memories.
* Exclude secrets.
* Avoid sending full documents.

Logs should not contain full prompts by default.

## 18. Model Testing

### Unit Tests
* Provider factory selects correct client.
* Missing API key raises `ConfigurationError`.
* Provider error maps to correct app exception.
* Token counting fallback works.
* JSON parsing rejects malformed output.

### Integration Tests with Mocked Providers
* Streaming chat yields token/done events.
* Embedding batch writes expected vectors.
* JSON task retries malformed response.
* Fallback provider used on transient failure.
* Cost analytics event written.

### Manual Tests
* OpenAI connection test.
* Anthropic connection test.
* Ollama unavailable message.
* Ollama available local chat.
* Embedding model switch and re-embedding warning.

## 19. Acceptance Checklist
Model integration is complete when:
1. Provider abstraction is implemented.
2. OpenAI chat and embeddings work.
3. Streaming is normalized and persisted.
4. JSON tasks validate with Pydantic.
5. Provider errors produce structured app errors.
6. Token/cost analytics are stored.
7. Settings page can test provider connection.
8. Ollama and Anthropic clients are either implemented or clearly deferred per roadmap phase.

