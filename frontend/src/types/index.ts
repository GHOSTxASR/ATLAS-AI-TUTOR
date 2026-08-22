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

export interface ApiResponse<T> {
  data: T;
  error: {
    code: string;
    message: string;
    details: any;
  } | null;
  meta: any;
}

export interface ChatSession {
  id: string;
  profile_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages?: ChatMessage[];
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

export type DocumentStatus = "pending" | "extracting" | "extracted" | "pending_ocr" | "error";

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
