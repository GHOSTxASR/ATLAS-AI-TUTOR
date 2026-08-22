## 2026-08-19T15:43:14Z
You are survey_frontend_1, an Explorer investigating the Frontend requirements R6-R9 for the AI TUTOR (LearningOS) project.

Project root: d:\AI TUTOR\LearningOS
Working directory for your metadata: d:\AI TUTOR\LearningOS\.agents\survey_frontend_1\
Mandatory specification file: d:\AI TUTOR\LearningOS\.agents\ORIGINAL_REQUEST.md

Your task:
1. Read d:\AI TUTOR\LearningOS\.agents\ORIGINAL_REQUEST.md completely.
2. Investigate frontend files related to:
   - R6: `frontend/src/stores/chatStore.ts` (WebSocket message handler for `type === "citations"` messages from backend, citations state storage and exposure).
   - R7: `frontend/src/api/client.ts` (shared axios client) and all modules currently creating their own instances (`chat.ts`, `documents.ts`, `profiles.ts`, `analytics.ts`, `graph.ts`, `memory.ts`, `notes.ts`, `quiz.ts`, `roadmap.ts`, `SettingsPage.tsx`).
   - R8: `frontend/src/pages/SettingsPage.tsx` (model catalog dropdown fetching from `GET /api/v1/settings/models?provider=...` with custom model fallback).
   - R9: `frontend/src/pages/DocumentsPage.tsx` (syllabus toggle during upload), `EmptyState` components across pages (`window.location.href` replaced with React Router `useNavigate()`), `frontend/src/pages/ChatPage.tsx` (`:sessionId` URL param and `?topic` query param handling for deep-linking).
3. Identify exact line numbers, component structures, state interactions, and recommended fix strategies.
4. Write your detailed findings to `d:\AI TUTOR\LearningOS\.agents\survey_frontend_1\analysis.md` and write a structured handoff report to `d:\AI TUTOR\LearningOS\.agents\survey_frontend_1\handoff.md`.
5. Send a completion message to parent when finished referencing the report paths.
