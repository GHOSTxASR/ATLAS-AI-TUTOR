# 15. UI/UX Specification

## 1. Purpose
This document defines the product experience, interaction model, visual system, and page-level acceptance criteria for Atlas. It expands the frontend architecture into concrete UI/UX instructions that a coding agent can implement without guessing.

Related documents:
* `00_IMPLEMENTATION_PLAN.md`: master source of truth.
* `04_API_SPECIFICATION.md`: backend payloads and WebSocket contracts.
* `05_FRONTEND_ARCHITECTURE.md`: frontend architecture and state ownership.
* `14_DEVELOPMENT_ROADMAP.md`: implementation sequence and phase gates.

## 2. Product Experience Goals
Atlas should feel like a focused local learning workspace, not a marketing website or generic chatbot.

Core experience goals:
* The first screen after setup should help the learner continue studying immediately.
* The app should make the current profile, current topic, document status, and next learning action obvious.
* The UI should support long study sessions with low visual noise.
* The tutor should feel central, but not isolated from documents, roadmap, memory, and progress.
* Every AI-generated artifact should be inspectable: citations, memories, roadmap nodes, quiz feedback, and graph links.

## 3. Information Architecture
Primary navigation lives in the left sidebar.

Required top-level pages:
| Route | Page | Primary Purpose |
| :--- | :--- | :--- |
| `/setup` | Setup | First profile, model provider, API key, defaults. |
| `/dashboard` | Dashboard | Learning overview and quick continuation. |
| `/chat` | Chat | AI tutor conversation and citations. |
| `/chat/:sessionId` | Chat Session | Specific persisted conversation. |
| `/roadmap` | Roadmap | Curriculum path, node status, active topic. |
| `/documents` | Documents | Upload, indexing status, source management. |
| `/graph` | Knowledge Graph | Concept map and relationship exploration. |
| `/quiz` | Quiz | Practice generation, active quiz, results. |
| `/analytics` | Analytics | Progress, mastery, velocity, weak areas. |
| `/memory` | Memory | View and edit learner memory. |
| `/settings` | Settings | Models, API keys, data paths, backups. |

Secondary UI surfaces:
* Context panel on the right.
* Modal dialogs for create/edit/delete confirmations.
* Toast notifications for short-lived success/failure updates.
* Inline error blocks for form and status problems.

## 4. Layout System

### Desktop Layout
Use a persistent three-zone layout:
| Zone | Width | Behavior |
| :--- | :--- | :--- |
| Sidebar | 240px fixed | Navigation, active profile, create/switch profile, app status. |
| Main content | Flexible | Current page workspace. |
| Context panel | 320px default | Route-specific details; collapsible. |

Desktop breakpoints:
* `>= 1280px`: sidebar, main, and context panel visible by default.
* `1024px-1279px`: context panel collapsed by default unless the page requires it.
* `< 1024px`: sidebar becomes drawer; context panel becomes slide-over.

### Mobile/Small Layout
Atlas is primarily desktop-first, but mobile should remain usable:
* Sidebar becomes bottom navigation or hamburger drawer.
* Context panel becomes a full-height sheet.
* Tables become stacked list rows.
* Graph and roadmap views must provide list alternatives.
* Chat input remains sticky at the bottom.

### Layout Stability
Fixed-format surfaces must not jump during loading or streaming:
* Chat message list reserves space for avatars/status.
* Roadmap node cards have stable min width and min height.
* Document status rows use fixed status badge width.
* Buttons have fixed icon/button dimensions.
* Progress indicators should update without changing row height.

## 5. Visual Design System

### Color Roles
Use semantic tokens instead of hard-coded colors in components.

Required tokens:
| Token | Purpose |
| :--- | :--- |
| `--color-bg` | App background. |
| `--color-surface` | Panels, toolbar surfaces. |
| `--color-surface-raised` | Modals and floating menus. |
| `--color-border` | Default border. |
| `--color-text` | Primary text. |
| `--color-text-muted` | Secondary text. |
| `--color-primary` | Primary actions and active navigation. |
| `--color-success` | Completed/indexed/mastered. |
| `--color-warning` | In progress, low confidence, queued. |
| `--color-danger` | Errors, deletion, weak mastery. |
| `--color-info` | Citations, neutral status, selected graph node. |

Avoid a one-note palette. The interface should rely on neutral surfaces with purposeful state colors.

### Typography
| Use | Font | Notes |
| :--- | :--- | :--- |
| UI text | Inter or system sans | Default for controls and page text. |
| Code/math/source snippets | Fira Code or system monospace | Used for code blocks and extracted source preview. |
| Chat markdown | UI font with readable line height | Preserve headings, lists, code, math. |

Rules:
* Do not scale font size with viewport width.
* Use `letter-spacing: 0`.
* Use tighter headings inside dashboards, cards, and panels.
* Avoid oversized hero text except setup welcome screens.

### Spacing and Radius
* Base spacing unit: 4px.
* Common gaps: 8px, 12px, 16px, 24px.
* Cards and panels: max 8px border radius.
* Icon buttons: square dimensions, usually 32px or 36px.
* Do not nest cards inside cards.

### Iconography
Use `lucide-react` icons.

Suggested icons:
| Action/Concept | Icon |
| :--- | :--- |
| New chat | `MessageSquarePlus` |
| Upload | `Upload` |
| Documents | `Files` |
| Roadmap | `Route` |
| Graph | `Network` |
| Memory | `Brain` |
| Analytics | `ChartLine` |
| Settings | `Settings` |
| Complete | `CheckCircle` |
| Skip | `Forward` |
| Flag | `Flag` |
| Delete | `Trash2` |
| Export | `Download` |
| Search | `Search` |
| Collapse panel | `PanelRightClose` |

Icon-only buttons require `aria-label` and tooltip.

## 6. Component Standards

### Buttons
Button variants:
* `primary`: main page action.
* `secondary`: alternative action.
* `ghost`: toolbar/icon action.
* `danger`: destructive action.
* `link`: text-level navigation.

Rules:
* Destructive actions require confirmation when data loss is possible.
* Loading state should disable duplicate submit.
* Button text must not wrap awkwardly; use shorter labels or icon buttons where needed.

### Forms
All forms must support:
* Label text.
* Optional help text.
* Inline validation error.
* Disabled/loading submit state.
* Keyboard submit where appropriate.

API key fields:
* Use password input by default.
* Provide show/hide toggle.
* After save, clear raw key from frontend state.
* Show masked status only.

### Tables and Lists
Use tables for dense operational pages:
* Documents.
* Memory.
* Quiz history.
* Settings model lists.

Tables should support:
* Empty state.
* Loading skeleton rows.
* Error row.
* Row actions in a stable right column.
* Pagination when record count exceeds page limit.

### Modals and Drawers
Use modals for confirmation and small forms. Use drawers/sheets for contextual details.

Rules:
* Trap focus.
* Close with Escape.
* Preserve unsaved edits until user confirms cancel.
* Avoid large nested workflows inside modals.

### Toasts
Use toasts for brief feedback only:
* Upload started.
* Profile saved.
* API key test passed/failed.
* Export complete.

Do not use toasts as the only place for important errors. Persistent errors need inline UI.

## 7. Page Specifications

### Setup Page
Purpose: turn a blank local install into a usable learning workspace.

Required sections:
1. Welcome and local-first note.
2. Model provider selector: OpenAI, Anthropic, Ollama.
3. API key entry for cloud providers.
4. Connection test.
5. First profile creation.
6. Default learning mode and pace/depth preferences.

Acceptance criteria:
* If no profile exists, `/` redirects to `/setup`.
* User can complete setup without editing files manually.
* API key is sent only to backend and cleared locally after save.
* Provider connection failure is shown inline with retry.
* Creating the first profile routes to `/dashboard`.

### Dashboard Page
Purpose: orient the learner and expose next actions.

Required widgets:
* Active profile header.
* Active roadmap progress.
* Continue current topic.
* Recent chat sessions.
* Document indexing status.
* Weak concepts.
* Quick actions: upload document, continue chat, generate roadmap, start quiz.

Acceptance criteria:
* Loading state does not show empty zero metrics.
* If no documents exist, primary action is upload.
* If documents exist but no roadmap exists, primary action is generate roadmap.
* If a roadmap exists, primary action is continue current/next node.

### Chat Page
Purpose: main AI tutor workspace.

Required zones:
* Session list or session drawer.
* Message stream.
* Sticky chat input.
* Mode selector.
* Citation/source context panel.
* Current roadmap node context.

Chat input requirements:
* Supports multiline text.
* Shows send button with icon.
* Disabled while no active profile exists.
* Shows streaming/cancel state while model responds.

Message requirements:
* User and assistant messages visually distinct.
* Assistant supports markdown, code blocks, math, and citations.
* Citations render as clickable markers.
* Streaming draft updates without layout jumps.
* Incomplete messages are marked after disconnect.

Acceptance criteria:
* WebSocket token stream renders live.
* `done` event replaces or confirms draft with persisted message.
* `error` event shows recoverable message and preserves user input.
* Citations open source preview in the context panel.

### Documents Page
Purpose: manage source materials.

Required features:
* Drag/drop upload.
* File picker fallback.
* Syllabus checkbox.
* Optional roadmap-node association.
* Document list with status.
* Progress display for extracting/chunking/indexing.
* Reprocess.
* Delete.
* Error details.

Acceptance criteria:
* Duplicate upload error is clear.
* Missing OCR dependency does not block text PDFs.
* Document deletion asks for confirmation.
* Status updates from polling and WebSocket do not conflict.

### Roadmap Page
Purpose: visualize and manage learning path.

Required views:
* MVP list/tree view.
* Phase 2 ReactFlow graph view.

Node states:
* `not_started`
* `locked`
* `in_progress`
* `completed`
* `skipped`
* `flagged`

Required interactions:
* Select node.
* Start node.
* Mark complete.
* Skip.
* Flag.
* Generate/regenerate roadmap.
* Toggle Strict/Adaptive/Hybrid during generation.

Acceptance criteria:
* Locked state explains missing prerequisites.
* Optimistic updates roll back on API failure.
* List view remains usable when graph view is too dense.
* Bridge nodes in Hybrid mode are visually distinct.

### Knowledge Graph Page
Purpose: explore concepts and relationships.

Required features:
* D3 force-directed graph.
* Search.
* Node type filters.
* Mastery filter.
* Weak concept highlighting.
* Selected node panel.
* List fallback.

Acceptance criteria:
* Initial render works for empty graph.
* Graph remains interactive for at least 1,000 nodes.
* Labels do not overlap critical controls.
* Keyboard/list fallback exposes the same selected-node details.

### Quiz Page
Purpose: practice and formal assessment.

Required states:
* Quiz setup.
* Active quiz.
* Timed assessment.
* Submitted results.
* History.

Acceptance criteria:
* Practice mode can show feedback after each answer.
* Assessment mode waits until final submission.
* Timer is visible and accessible.
* Results show score, feedback, mastery effect, and next recommendation.

### Analytics Page
Purpose: inspect progress and learning patterns.

Required widgets:
* Mastery by subject/topic.
* Learning velocity.
* Activity heatmap.
* Weakness list.
* Study time.
* Model usage/cost estimate.

Acceptance criteria:
* Empty analytics state suggests first action.
* Charts have accessible labels and table fallback.
* Values match `AnalyticsService` output, not frontend recomputation of business rules.

### Memory Page
Purpose: let the learner inspect and control what the system remembers.

Required features:
* Category filter.
* Confidence filter.
* Search.
* Inline edit.
* Delete.
* Manual add.
* Provenance display.

Acceptance criteria:
* User can delete false memories.
* Deleted memories disappear from retrieval.
* Manual memories are marked as manual.
* Privacy note is visible without being alarmist.

### Settings Page
Purpose: configure local runtime.

Required sections:
* Model provider.
* API keys.
* Embedding model.
* Data directory display.
* OCR path.
* Backup settings.
* Export/import.
* Connection tests.

Acceptance criteria:
* Raw API keys never persist in frontend state.
* Model change warns when re-embedding may be required.
* Connection test shows provider-specific error.
* Data directory is display-only unless a migration flow exists.

## 8. Loading, Empty, Error, and Offline States

### Loading
Use skeletons for:
* Dashboard widgets.
* Documents table.
* Chat session list.
* Roadmap list.
* Memory table.

Use progress bars for:
* Upload.
* Extraction.
* Indexing.
* Export.

### Empty States
Every major page needs an empty state with one clear action:
| Page | Empty Action |
| :--- | :--- |
| Dashboard | Create/upload/continue depending on state. |
| Documents | Upload a document. |
| Chat | Start a new chat. |
| Roadmap | Generate roadmap. |
| Graph | Index documents or study topics. |
| Quiz | Generate quiz. |
| Memory | Add memory or continue chatting. |
| Analytics | Study/upload first. |

### Error States
Error UI should show:
* Human-readable message.
* Optional technical details in collapsible area.
* Retry action when retryable.
* Link/action to relevant settings if configuration is missing.

### Backend Offline
If `GET /api/v1/health` fails:
* Show connection error page.
* Provide retry.
* Do not route to setup.
* Do not clear local profile state.

## 9. Accessibility Requirements
Baseline WCAG target: WCAG 2.1 AA where practical.

Requirements:
* All controls keyboard reachable.
* Focus indicator visible.
* Icon-only buttons have accessible names.
* Modal focus trap.
* Color contrast AA for text.
* Status colors paired with text/icons.
* Canvas-heavy views have list fallback.
* Live chat streaming uses polite `aria-live` where appropriate.
* Form errors are linked to inputs with `aria-describedby`.

## 10. Interaction Details

### Keyboard Shortcuts
MVP shortcuts:
| Shortcut | Action |
| :--- | :--- |
| `Ctrl+K` | Open global search or command palette. |
| `Ctrl+N` | New chat when on chat page. |
| `Ctrl+Enter` | Send chat message. |
| `Esc` | Close modal/drawer. |

Do not display a large shortcut tutorial in-app. Tooltips can mention shortcuts.

### Context Panel Behavior
The right panel changes by route:
| Route | Context Panel |
| :--- | :--- |
| Chat | Citations, active roadmap node, relevant memories. |
| Roadmap | Selected node details and actions. |
| Documents | Selected document status and extracted text preview. |
| Graph | Selected concept details. |
| Quiz | Current topic, timer, scoring summary. |
| Memory | Selected memory provenance. |

Panel state persists per user preference.

### Confirmation Rules
Require confirmation for:
* Delete profile.
* Delete document.
* Delete chat session.
* Delete memory.
* Regenerate roadmap when it archives current roadmap.
* Change embedding model when re-embedding is needed.

## 11. Visual QA Checklist
Before considering frontend work done:
* Desktop screenshot at 1440x900.
* Laptop screenshot at 1280x720.
* Tablet/small screenshot around 900px width.
* Mobile narrow screenshot around 390px width.
* No text overlap.
* Buttons fit text.
* Tables/list rows stable during loading.
* Chat streaming does not jump unexpectedly.
* Context panel collapse/expand works.
* Empty and error states are polished.

## 12. Implementation Acceptance Checklist
UI/UX work is complete when:
1. All routes render with loading, empty, error, and populated states.
2. All API calls go through typed wrappers.
3. All profile-scoped queries wait for active profile ID.
4. Core actions are keyboard accessible.
5. Icon-only controls have labels/tooltips.
6. The app works from production Vite build served by FastAPI.
7. Playwright covers setup, upload, chat, and roadmap happy paths.

