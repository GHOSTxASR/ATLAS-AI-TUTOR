import { apiClient } from "./client";
import {
  ApiResponse,
  ChatMessage,
  ChatMessageCreate,
  ChatSession,
  ChatSessionCreate,
  ChatSessionUpdate,
  Citation,
} from "../types";

export type LearningMode =
  | "teaching"
  | "revision"
  | "summary"
  | "general_knowledge"
  | "quiz"
  | "assessment";

export interface TutorChatRequest {
  session_id?: string;
  content: string;
  mode?: LearningMode;
  document_ids?: string[];
  roadmap_node_id?: string;
}

export interface TutorChatResponse {
  session_id: string;
  message_id: string;
  content: string;
  mode: LearningMode;
  citations: Citation[];
}

export interface UnifiedLearningContext {
  profile_id: string;
  profile_name: string;
  profile_type: string;
  mode: string;
  system_prompt: string;
  memory: {
    strengths: string[];
    weaknesses: string[];
    learning_style?: string;
    recent_notes?: string[];
  };
  roadmap: {
    roadmap_title?: string;
    mode?: string;
    active_topic?: string;
    mastery_score: number;
    status: string;
    prerequisites: string[];
    next_topics: string[];
  };
  graph: {
    matched_concept?: string;
    concept_description?: string;
    mastery_score: number;
    mention_count: number;
    prerequisite_concepts: string[];
    related_concepts: string[];
    connected_documents: string[];
  };
  syllabus: {
    syllabus_title?: string;
    current_chapter?: string;
    covered_subtopics: string[];
  };
  citations: Citation[];
  total_tokens: number;
}

export const chatApi = {
  getSessions: async (profileId: string, query?: string): Promise<ChatSession[]> => {
    const params = query ? { q: query } : {};
    const response = await apiClient.get<ApiResponse<ChatSession[]>>(
      `/profiles/${profileId}/sessions`,
      { params }
    );
    return response.data.data;
  },

  getSession: async (profileId: string, sessionId: string): Promise<ChatSession> => {
    const response = await apiClient.get<ApiResponse<ChatSession>>(
      `/profiles/${profileId}/sessions/${sessionId}`
    );
    return response.data.data;
  },

  createSession: async (profileId: string, data: ChatSessionCreate): Promise<ChatSession> => {
    const response = await apiClient.post<ApiResponse<ChatSession>>(
      `/profiles/${profileId}/sessions`,
      data
    );
    return response.data.data;
  },

  updateSession: async (
    profileId: string,
    sessionId: string,
    data: ChatSessionUpdate
  ): Promise<ChatSession> => {
    const response = await apiClient.patch<ApiResponse<ChatSession>>(
      `/profiles/${profileId}/sessions/${sessionId}`,
      data
    );
    return response.data.data;
  },

  deleteSession: async (profileId: string, sessionId: string): Promise<void> => {
    await apiClient.delete(`/profiles/${profileId}/sessions/${sessionId}`);
  },

  addMessage: async (
    profileId: string,
    sessionId: string,
    data: ChatMessageCreate
  ): Promise<ChatMessage> => {
    const response = await apiClient.post<ApiResponse<ChatMessage>>(
      `/profiles/${profileId}/sessions/${sessionId}/messages`,
      data
    );
    return response.data.data;
  },

  tutorChat: async (
    profileId: string,
    data: TutorChatRequest
  ): Promise<TutorChatResponse> => {
    const response = await apiClient.post<ApiResponse<TutorChatResponse>>(
      `/profiles/${profileId}/tutor/chat`,
      data
    );
    return response.data.data;
  },

  getUnifiedContext: async (
    profileId: string,
    params?: { q?: string; mode?: string; roadmap_node_id?: string }
  ): Promise<UnifiedLearningContext> => {
    const response = await apiClient.get<ApiResponse<UnifiedLearningContext>>(
      `/profiles/${profileId}/tutor/context`,
      { params }
    );
    return response.data.data;
  },
};
