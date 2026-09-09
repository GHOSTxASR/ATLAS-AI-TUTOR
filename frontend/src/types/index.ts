import type { ApiEnvelope } from "../api/client";

export type ProfileType = "JEE" | "GATE" | "Semester Study" | "Custom Learning";

export interface Profile {
  id: string;
  name: string;
  profile_type: ProfileType;
  created_at: string;
  updated_at: string;
}

export interface ProfileCreate {
  name: string;
  profile_type: ProfileType;
}

export interface ProfileUpdate {
  name?: string;
  profile_type?: ProfileType;
}

/**
 * The response envelope every endpoint returns.
 *
 * An alias rather than a second declaration: this used to be a looser copy of
 * `ApiEnvelope` with `any` where that has `Record<string, unknown>`, so the
 * two could drift and half the codebase got the weaker types.
 */
export type ApiResponse<T> = ApiEnvelope<T>;

export interface ChatSession {
  id: string;
  profile_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages?: ChatMessage[];
  /** Roadmap topic this thread belongs to, when opened from one. */
  roadmap_node_id?: string | null;
}

export interface ChatSessionCreate {
  title?: string;
}

export interface ChatSessionUpdate {
  title: string;
}

export type RoleLiteral = "user" | "assistant";

/**
 * Mirrors the backend `CitationTracker.Citation.to_dict()` payload exactly.
 * The previous shape (`source_index` / `source_label` / `doc_id`) matched no
 * field the API sends, so every citation rendered as `undefined`.
 */
export interface Citation {
  index: number;
  source_type: "document" | "memory" | "note" | "chat_summary" | "graph_node" | string;
  source_id: string;
  filename: string;
  page_number: number | null;
  char_offset_start: number;
  char_offset_end: number;
  snippet: string;
  score: number;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: RoleLiteral;
  content: string;
  created_at: string;
  updated_at: string;
  /** Only present for messages received live; not persisted server-side yet. */
  citations?: Citation[];
}

export interface ChatMessageCreate {
  role: RoleLiteral;
  content: string;
}

export type DocumentFileType = "pdf" | "docx" | "txt" | "image";

/**
 * Mirrors DocumentStatus in backend/app/schemas/document.py.
 *
 * Four of these were missing here -- including "indexed", the terminal success
 * state nearly every document ends in. Anything comparing a status against it
 * failed to typecheck, and anything switching on status silently had no branch
 * for the most common value.
 */
export type DocumentStatus =
  | "pending"
  | "extracting"
  | "extracted"
  | "pending_ocr"
  | "chunking"
  | "queuing"
  | "indexing"
  | "indexed"
  | "error";

export interface Document {
  id: string;
  profile_id: string;
  filename: string;
  file_type: DocumentFileType;
  status: DocumentStatus;
  page_count: number | null;
  chunk_count: number;
  word_count: number | null;
  is_syllabus: boolean;
  roadmap_node_id: string | null;
  uploaded_at: string;
  indexed_at: string | null;
  error_message: string | null;
}

export interface DocumentStatusInfo {
  id: string;
  status: DocumentStatus;
  page_count: number | null;
  word_count: number | null;
  chunk_count: number;
  error_message: string | null;
}
