import { apiClient, ApiEnvelope } from "./client";

export type NoteType = "lesson_note" | "revision_note" | "cheat_sheet" | "summary";
export type NoteSource = "ai_generated" | "user_written";

export interface NoteResponse {
  id: string;
  profile_id: string;
  roadmap_node_id?: string | null;
  title: string;
  content: string;
  note_type: NoteType;
  source: NoteSource;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface NoteSummary {
  id: string;
  profile_id: string;
  roadmap_node_id?: string | null;
  title: string;
  note_type: NoteType;
  source: NoteSource;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export const notesApi = {
  generateNote: async (
    profileId: string,
    payload: {
      topic_title?: string;
      roadmap_node_id?: string;
      note_type?: NoteType;
      custom_instructions?: string;
      document_ids?: string[];
    }
  ): Promise<NoteResponse> => {
    const res = await apiClient.post<ApiEnvelope<NoteResponse>>(
      `/profiles/${profileId}/notes/generate`,
      payload
    );
    return res.data.data;
  },

  listNotes: async (
    profileId: string,
    params?: { note_type?: string; roadmap_node_id?: string; q?: string }
  ): Promise<NoteSummary[]> => {
    const res = await apiClient.get<ApiEnvelope<NoteSummary[]>>(
      `/profiles/${profileId}/notes`,
      { params }
    );
    return res.data.data;
  },

  getNote: async (profileId: string, noteId: string): Promise<NoteResponse> => {
    const res = await apiClient.get<ApiEnvelope<NoteResponse>>(
      `/profiles/${profileId}/notes/${noteId}`
    );
    return res.data.data;
  },

  createUserNote: async (
    profileId: string,
    payload: {
      title: string;
      content: string;
      note_type?: NoteType;
      roadmap_node_id?: string;
      tags?: string[];
    }
  ): Promise<NoteResponse> => {
    const res = await apiClient.post<ApiEnvelope<NoteResponse>>(
      `/profiles/${profileId}/notes`,
      payload
    );
    return res.data.data;
  },

  updateNote: async (
    profileId: string,
    noteId: string,
    payload: {
      title?: string;
      content?: string;
      note_type?: NoteType;
      tags?: string[];
    }
  ): Promise<NoteResponse> => {
    const res = await apiClient.patch<ApiEnvelope<NoteResponse>>(
      `/profiles/${profileId}/notes/${noteId}`,
      payload
    );
    return res.data.data;
  },

  deleteNote: async (profileId: string, noteId: string): Promise<boolean> => {
    const res = await apiClient.delete<ApiEnvelope<{ deleted: boolean }>>(
      `/profiles/${profileId}/notes/${noteId}`
    );
    return res.data.data.deleted;
  },
};
