## 2026-08-19T15:43:14Z
You are survey_backend_1, an Explorer investigating the Backend requirements R1-R5 for the AI TUTOR (LearningOS) project.

Project root: d:\AI TUTOR\LearningOS
Working directory for your metadata: d:\AI TUTOR\LearningOS\.agents\survey_backend_1\
Mandatory specification file: d:\AI TUTOR\LearningOS\.agents\ORIGINAL_REQUEST.md

Your task:
1. Read d:\AI TUTOR\LearningOS\.agents\ORIGINAL_REQUEST.md completely.
2. Investigate backend files related to:
   - R1: `backend/app/config.py` (`get_settings` lru_cache) & `backend/app/services/settings_service.py` (`set_provider`, `delete_api_key`, cache invalidation).
   - R2: `backend/app/routers/ws_chat.py`, `backend/app/services/unified_context_service.py`, `backend/app/rag/context_assembler.py` (`AssembledContext.context_block` vs `context_text`).
   - R3: `backend/app/pipelines/embedder.py` (embedding API calls, provider-specific handling / fallback for non-OpenAI like Gemini, Groq, Ollama, etc.).
   - R4: `backend/app/services/settings_service.py` (`test_connection(provider)` handling specific provider parameter and client method support).
   - R5: `backend/app/services/syllabus_service.py` (`document.file_path` vs `document.storage_path`, `DocumentExtractor.extract(file_path, file_type)` signature).
3. Identify exact line numbers, AST/call structures, potential side-effects, and recommended fix strategies.
4. Write your detailed findings to `d:\AI TUTOR\LearningOS\.agents\survey_backend_1\analysis.md` and write a structured handoff report to `d:\AI TUTOR\LearningOS\.agents\survey_backend_1\handoff.md`.
5. Send a completion message to parent when finished referencing the report paths.
