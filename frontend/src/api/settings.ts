import { apiClient } from "./client";
import { ApiResponse } from "../types";

/**
 * Mirrors the payload built by `SettingsService.list_providers()`.
 * The previous declaration used `name`/`has_key`/`models`, none of which the
 * API returns, so every field read through this module was `undefined`.
 */
export interface ProviderItem {
  id: string;
  label: string;
  env_key: string;
  default_model: string;
  docs_url: string;
  key_set: boolean;
  active: boolean;
}

export interface ProvidersData {
  providers: ProviderItem[];
  active_provider: string;
  active_model: string;
}

export interface ModelInfo {
  id: string;
  label: string;
  free: boolean;
  context_length?: number | null;
}

export interface ModelCatalogResponse {
  provider: string;
  models: ModelInfo[];
  /** "live" when fetched from the provider, "fallback" for the static list. */
  source: "live" | "fallback";
  error?: string | null;
  free_count: number;
}

/** `SettingsService.test_connection()` reports `status`, not `success`. */
export interface TestConnectionResponse {
  status: "ok" | "error";
  provider: string;
  model_info?: { provider: string; model: string };
  error?: string;
}

export interface EmbeddingCatalogResponse extends ModelCatalogResponse {
  /** Embedding model that would be used right now. */
  active_model: string;
  /** Models the existing vector index was actually built with. */
  indexed_models: string[];
  /** True when the active model differs from what is indexed. */
  reindex_required: boolean;
}

export interface SetProviderRequest {
  provider: string;
  model?: string;
  api_key?: string;
  embedding_model?: string;
}

export interface SetProviderResponse {
  provider: string;
  model: string;
  key_persisted: boolean;
  message: string;
}

export const settingsApi = {
  getProviders: async (): Promise<ProvidersData> => {
    const response = await apiClient.get<ApiResponse<ProvidersData>>("/settings/providers");
    return response.data.data;
  },

  getModels: async (provider?: string, refresh = false): Promise<ModelCatalogResponse> => {
    const response = await apiClient.get<ApiResponse<ModelCatalogResponse>>("/settings/models", {
      params: { ...(provider ? { provider } : {}), ...(refresh ? { refresh: true } : {}) },
    });
    return response.data.data;
  },

  getEmbeddingModels: async (
    provider?: string,
    refresh = false
  ): Promise<EmbeddingCatalogResponse> => {
    const response = await apiClient.get<ApiResponse<EmbeddingCatalogResponse>>(
      "/settings/embedding-models",
      { params: { ...(provider ? { provider } : {}), ...(refresh ? { refresh: true } : {}) } }
    );
    return response.data.data;
  },

  setProvider: async (data: SetProviderRequest): Promise<SetProviderResponse> => {
    const response = await apiClient.post<ApiResponse<SetProviderResponse>>(
      "/settings/provider",
      data
    );
    return response.data.data;
  },

  /**
   * `apiKey` lets the caller test a key that has been typed but not saved.
   * Without it the endpoint tests the stored key, so testing a freshly pasted
   * key reported "not configured" until you pressed Save first.
   */
  testConnection: async (
    provider?: string,
    apiKey?: string
  ): Promise<TestConnectionResponse> => {
    const response = await apiClient.post<ApiResponse<TestConnectionResponse>>(
      "/settings/test-connection",
      { provider, api_key: apiKey || undefined }
    );
    return response.data.data;
  },

  deleteApiKey: async (provider: string): Promise<void> => {
    await apiClient.delete("/settings/apikey", { params: { provider } });
  },
};
