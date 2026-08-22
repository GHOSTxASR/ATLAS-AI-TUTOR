import axios from "axios";

export interface ApiEnvelope<T> {
  data: T;
  error: null | {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
  meta: null | Record<string, unknown>;
}

export interface HealthResponse {
  status: string;
  name: string;
  version: string;
  environment: string;
}

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api/v1"
});

export async function getHealth(): Promise<HealthResponse> {
  const response = await apiClient.get<ApiEnvelope<HealthResponse>>("/health");
  return response.data.data;
}

