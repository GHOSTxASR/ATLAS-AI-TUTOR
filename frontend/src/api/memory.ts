import { apiClient, ApiEnvelope } from "./client";

export type MemoryCategory =
  | "weakness"
  | "strength"
  | "preference"
  | "fact"
  | "misconception"
  | "goal";

export interface MemoryRecord {
  id: string;
  profile_id: string;
  category: MemoryCategory;
  subject: string;
  content: string;
  confidence: number;
  decay_factor: number;
  last_accessed: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export const memoryApi = {
  listMemories: async (
    profileId: string,
    params?: { category?: string; min_confidence?: number }
  ): Promise<MemoryRecord[]> => {
    const res = await apiClient.get<ApiEnvelope<MemoryRecord[]>>(
      `/profiles/${profileId}/memory`,
      { params }
    );
    return res.data.data;
  },

  createMemory: async (
    profileId: string,
    payload: {
      category: MemoryCategory;
      subject: string;
      content: string;
      confidence?: number;
      is_active?: boolean;
    }
  ): Promise<MemoryRecord> => {
    const res = await apiClient.post<ApiEnvelope<MemoryRecord>>(
      `/profiles/${profileId}/memory`,
      payload
    );
    return res.data.data;
  },

  updateMemory: async (
    profileId: string,
    memoryId: string,
    payload: {
      category?: MemoryCategory;
      subject?: string;
      content?: string;
      confidence?: number;
      is_active?: boolean;
    }
  ): Promise<MemoryRecord> => {
    const res = await apiClient.patch<ApiEnvelope<MemoryRecord>>(
      `/profiles/${profileId}/memory/${memoryId}`,
      payload
    );
    return res.data.data;
  },

  deleteMemory: async (profileId: string, memoryId: string): Promise<void> => {
    await apiClient.delete(`/profiles/${profileId}/memory/${memoryId}`);
  },
};
