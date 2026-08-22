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

export interface ModelCatalogResponse {
  provider: string;
  models: string[];
}

/** `SettingsService.test_connection()` reports `status`, not `success`. */
export interface TestConnectionResponse {
  status: "ok" | "error";
  provider: string;
  model_info?: { provider: string; model: string };
  error?: string;
}

export interface SetProviderRequest {
  provider: string;
  model?: string;
  api_key?: string;
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

  getModels: async (provider?: string): Promise<ModelCatalogResponse> => {
    const response = await apiClient.get<ApiResponse<ModelCatalogResponse>>("/settings/models", {
      params: provider ? { provider } : undefined,
    });
    return response.data.data;
  },

  setProvider: async (data: SetProviderRequest): Promise<SetProviderResponse> => {
    const response = await apiClient.post<ApiResponse<SetProviderResponse>>(
      "/settings/provider",
      data
    );
    return response.data.data;
  },

  testConnection: async (provider?: string): Promise<TestConnectionResponse> => {
    const response = await apiClient.post<ApiResponse<TestConnectionResponse>>(
      "/settings/test-connection",
      { provider }
    );
    return response.data.data;
  },

  deleteApiKey: async (provider: string): Promise<void> => {
    await apiClient.delete("/settings/apikey", { params: { provider } });
  },
};
