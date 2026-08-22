# 05. Frontend Architecture

## 1. Frontend Overview
LearningOS uses a Single Page Application (SPA) architecture built with React 18, TypeScript, and Vite. It runs locally and communicates exclusively with the local FastAPI backend on `http://localhost:8000`.

## 2. Technology Stack
| Library | Version | Purpose |
| :--- | :--- | :--- |
| React | 18.3 | Core UI framework |
| TypeScript | 5.4 | Static typing |
| Vite | 5.2 | Fast build tool and dev server |
| React Router | 6.23 | Client-side routing |
| Zustand | 4.5 | Global state management (profiles, UI state) |
| TanStack Query | 5.40 | Server state, caching, data fetching |
| Axios | 1.7 | REST API client |
| D3.js | 7.9 | Custom force-directed Knowledge Graph visualization |
| React Flow | 11.11 | Roadmap DAG visualization |
| Recharts | 4.4 | Analytics charts |
| Monaco Editor | 0.49 | Code editing and markdown note-taking |
| React Markdown | 9.0 | Rendering AI chat responses |
| Highlight.js | 11.9 | Syntax highlighting in markdown |
| KaTeX | 0.16 | Math equation rendering |
| Lucide React | 0.383 | Consistent icon set |
| date-fns | 3.6 | Date formatting and manipulation |
| React Hot Toast| 2.4 | Notifications |

## 3. Page/Route Map
1.  `/`: Redirects to `/dashboard` or `/setup` if no profile exists.
2.  `/setup`: Initial application setup (API keys, profile creation).
3.  `/dashboard`: Overview of current learning progress.
4.  `/chat`: Main AI Tutor interface (streaming chat).
5.  `/chat/:sessionId`: Specific chat session.
6.  `/roadmap`: Roadmap visualization (Strict/Adaptive/Hybrid).
7.  `/documents`: Document upload, management, and status viewing.
8.  `/graph`: Knowledge Graph D3 visualization.
9.  `/quiz`: Quiz history and generation.
10. `/quiz/:quizId`: Active quiz taking interface.
11. `/analytics`: Charts and mastery metrics.
12. `/memory`: View and edit extracted AI memories.
13. `/settings`: Configuration, model selection, API keys.

## 4. Complete Component Hierarchy
```text
App
├── QueryClientProvider
├── RouterProvider
└── MainLayout
    ├── Sidebar (Navigation)
    ├── MainContent (Dynamic Route Rendering)
    │   ├── DashboardPage
    │   ├── ChatPage
    │   │   ├── ChatSessionList
    │   │   ├── MessageStream
    │   │   │   └── MessageBubble (ReactMarkdown)
    │   │   └── ChatInputArea
    │   ├── RoadmapPage
    │   │   ├── ModeSelector
    │   │   └── ReactFlowCanvas
    │   ├── GraphPage
    │   │   ├── FilterPanel
    │   │   └── D3Canvas
    │   └── ...other pages
    └── ContextPanel (Dynamic based on route, e.g., NodeDetails, DocumentStatus)
```

## 5. Design System
*   **Color Palette**: Neutral dark grays (e.g., `#121212`, `#1E1E1E`), primary accent colors for states (Blue `#3B82F6` for info, Green `#10B981` for completed, Red `#EF4444` for weakness).
*   **Typography**: `Inter` for UI, `Fira Code` for code blocks.
*   **Spacing System**: 4px base unit (`p-1` = 4px, `p-4` = 16px).
*   **Animations**: Minimalist, fast transitions (150ms-200ms) for hover states and modal popups. CSS custom properties map these tokens globally.

## 6. Layout System
A persistent Three-Panel Layout:
1.  **Sidebar (Left, 240px)**: Navigation links, active profile switcher, new chat button.
2.  **Main Content (Center, flex-1)**: The primary workspace (Chat stream, Graph, or Roadmap).
3.  **Context Panel (Right, 320px)**: Context-aware sidebar. In Chat, shows RAG citations and current Roadmap Node. In Graph, shows selected node details. Can be toggled closed.

## 7. State Management (Zustand Stores)
*   `useProfileStore`: Stores the `activeProfileId`. Used by almost every API request as a header/param.
*   `useChatStore`: Stores current `sessionId`, `chatMode` (Deep Learning, Quiz, etc.).
*   `useUiStore`: Manages Context Panel visibility, theme (dark/light), and modal states.
*   `useSettingsStore`: Caches local UI preferences.

## 8. TanStack Query Strategy
*   **Query Keys**: Structured as `['domain', profileId, resourceId]`. E.g., `['documents', 'profile-123']`.
*   **StaleTime**: Default 5 minutes. Real-time data (chat) uses WebSockets.
*   **Mutations**: On success, `queryClient.invalidateQueries({ queryKey: [...] })` is called to automatically refetch lists.

## 9. API Client Layer
Configured in `src/api/client.ts`. Axios instance with a base URL of `http://localhost:8000/api/v1`.
Interceptors automatically unwrap the `{ data, error }` envelope, throwing the `error` so TanStack Query can catch it.

## 10. Custom Hooks
*   `useChat()`: Manages message history list, pagination, and sends queries.
*   `useStreaming()`: Manages the WebSocket connection, appending tokens to the active message state in real-time.
*   `useRoadmap()`: Fetches DAG, handles node status updates.
*   `useGraph()`: Fetches node/edge data, formats it for D3.

## 11. WebSocket Streaming
`useStreaming` Hook Logic:
1. Connects to `ws://localhost:8000/ws/chat/{sessionId}`.
2. On message, parses JSON.
3. If `type === 'token'`, appends string to a local React state holding the 'streaming message'.
4. If `type === 'done'`, triggers TanStack Query invalidation to fetch the final saved message from the DB.

## 12. Component Patterns
*   **Loading Skeletons**: Used instead of spinners for list views (Documents, Chat Sessions).
*   **Error Boundaries**: Wrap major route components to prevent full app crashes.
*   **Optimistic Updates**: Used when changing Roadmap node status. UI updates instantly, rolls back if API fails.

## 13. Each Page Component Details
*   **Dashboard**: Fetches `/analytics/overview`, renders high-level stats and recent activity.
*   **Documents**: Renders an upload dropzone. Fetches `/documents`. Polling enabled if any document status is `extracting` or `embedding`.
*   **Memory**: Table view of `/memory`. Allows inline editing of records.
*   **Settings**: Form inputs mapping to `/settings`. Handles test connection button for AI providers.

## 14. Chat Page Deep Dive
The core UI. Consists of a scrolling `MessageStream`. When a user types, a temporary "assistant" message block is rendered. As WebSocket tokens arrive, `ReactMarkdown` renders the text in real-time. Citations are displayed as small superscript clickable badges `[1]`, which open the source text in the Context Panel.

## 15. Graph Page Deep Dive
Uses a custom React component wrapping vanilla `D3.js`.
*   `simulation`: Runs a force-directed layout on a WebWorker to prevent UI freezing.
*   `zoom controls`: D3-zoom behavior integrated.
*   Clicks update the `selectedNode` state, which drives the Context Panel rendering.

## 16. Roadmap Page Deep Dive
Uses `ReactFlow`. Nodes are custom components showing status icons (Checkmark, Play, Lock). Edges use bezier curves. The Context Panel shows syllabus descriptions and allows status updates.

## 17. TypeScript Types
Defined in `src/types/index.ts`, exactly mirroring the Pydantic schemas in the backend. Ensures end-to-end type safety.
E.g., `export interface Document { id: string; filename: string; status: DocumentStatus; ... }`

## 18. Error Handling
Global Axios interceptor catches network errors (e.g., backend down) and triggers a red `react-hot-toast` notification. Specific API errors (e.g., Validation) are handled inline near the relevant form.

## 19. Performance Optimizations
*   `React.memo` used heavily on Chat Messages and React Flow nodes to prevent unnecessary re-renders.
*   Code splitting via `React.lazy()` for major routes (Graph and Roadmap libraries are heavy).
*   Debounced search inputs.

## 20. Build Configuration
`vite.config.ts` includes a proxy rule:
```typescript
server: {
  proxy: {
    '/api': 'http://127.0.0.1:8000',
    '/ws': { target: 'ws://127.0.0.1:8000', ws: true }
  }
}
```
This avoids CORS issues entirely during local development. In production `npm run build`, the output is served natively by FastAPI.

## 21. Master Plan Implementation Addendum

### Route Guards and First-Run Behavior
*   On app load, call `GET /api/v1/profiles`.
*   If no profiles exist, route `/` to `/setup`.
*   If profiles exist but no active profile is set in local storage, select the backend `is_active` profile or the first profile.
*   All profile-scoped pages must block data fetching until `activeProfileId` is known.
*   If the backend is unreachable, show a full-page local connection error with a retry action. Do not silently redirect to setup.

### Required TypeScript Domains
Create a type file or exported type section for:
*   `Profile`, `ProfileCreate`, `ProfileUpdate`
*   `Document`, `DocumentStatus`, `DocumentUploadOptions`
*   `ChatSession`, `ChatMessage`, `StreamingEvent`
*   `Roadmap`, `RoadmapNode`, `RoadmapEdge`, `RoadmapMode`, `RoadmapNodeStatus`
*   `GraphNode`, `GraphEdge`, `GraphResponse`
*   `MemoryRecord`, `MemoryCategory`
*   `QuizAttempt`, `QuizQuestion`, `QuizResult`
*   `AnalyticsOverview`, `MasteryPoint`, `VelocityPoint`, `WeaknessSummary`
*   `Settings`, `ModelProvider`, `ApiKeyStatus`

These types must mirror backend Pydantic response schemas. If a backend schema changes, update the frontend type in the same change.

### UI State Ownership
| State | Owner | Persistence |
| :--- | :--- | :--- |
| Active profile ID | `useProfileStore` | localStorage plus backend `is_active` update |
| Current chat session | `useChatStore` | URL when possible, localStorage fallback |
| Context panel open/closed | `useUiStore` | localStorage |
| Theme | `useUiStore` | localStorage |
| Server data | TanStack Query | Query cache only |
| Streaming assistant draft | `useStreaming` local state | Not persisted until backend `done` |

Do not duplicate server records in Zustand. Zustand should hold UI/session state; TanStack Query should own server cache.

### Page-Level Acceptance Criteria
*   `SetupPage`: can create first profile, save/test API key, choose provider/model, and recover from validation errors inline.
*   `DashboardPage`: shows progress summary, active roadmap, recent sessions, document indexing status, and top weak concepts.
*   `DocumentsPage`: supports drag/drop upload, syllabus checkbox, per-document status, error display, reprocess, delete, and progress updates.
*   `ChatPage`: supports session list, streaming, citations, mode switcher, current roadmap node display, reconnect handling, and export.
*   `RoadmapPage`: supports list view for MVP, ReactFlow graph view for Phase 2, node detail panel, mark complete, skip, flag, and regenerate.
*   `GraphPage`: supports pan/zoom, search, filters, selected node panel, and weak-topic highlighting.
*   `QuizPage`: supports quiz generation, answer submission, timer for assessment mode, results, and mastery update display.
*   `MemoryPage`: supports category filter, confidence filter, edit, delete, and manual add.
*   `SettingsPage`: supports model provider settings, encrypted API key update/delete, connection test, data path display, and backup/export actions.

### Loading, Empty, and Error States
Every page must implement all three states:
*   Loading: skeletons for list/table/content areas.
*   Empty: useful action, such as "Upload a document" or "Create a roadmap".
*   Error: backend message, retry action, and no broken layout.

### Accessibility and Keyboard Baseline
*   All icon-only buttons must have `aria-label` and tooltip text.
*   Modal dialogs must trap focus and close on `Escape`.
*   Graph and roadmap canvases must provide a list/table fallback for keyboard users.
*   Color must not be the only indicator for node status; include icon and text in detail panels.
*   Chat input submits with `Ctrl+Enter` and inserts newline with `Enter` only if multiline mode is active.

### Frontend Test Targets
*   API client envelope unwrapping and error normalization.
*   `useStreaming` event handling for `token`, `citations`, `done`, and `error`.
*   Roadmap optimistic update rollback.
*   Document upload status polling/WebSocket progress merge.
*   Route guard behavior for no profile, active profile, and backend offline states.
