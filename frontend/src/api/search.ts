import { apiClient, ApiEnvelope } from "./client";

export type GlobalCategory = "chats" | "notes" | "documents" | "graph" | "roadmap";

export interface GlobalSearchResultItem {
  id: string;
  title: string;
  subtitle?: string;
  snippet: string;
  category: GlobalCategory;
  url_path: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface GlobalSearchResponse {
  query: string;
  total_results: number;
  chats: GlobalSearchResultItem[];
  notes: GlobalSearchResultItem[];
  documents: GlobalSearchResultItem[];
  graph: GlobalSearchResultItem[];
  roadmap: GlobalSearchResultItem[];
}

export const searchApi = {
  globalSearch: async (
    profileId: string,
    query: string,
    params?: { limit?: number; categories?: GlobalCategory[]; include_semantic?: boolean }
  ): Promise<GlobalSearchResponse> => {
    const res = await apiClient.post<ApiEnvelope<GlobalSearchResponse>>(
      `/profiles/${profileId}/search/global`,
      {
        query,
        limit_per_category: params?.limit || 5,
        categories: params?.categories,
        include_semantic: params?.include_semantic ?? true,
      }
    );
    return res.data.data;
  },
};
