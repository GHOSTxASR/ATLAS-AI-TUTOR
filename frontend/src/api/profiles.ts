import { apiClient } from "./client";
import { ApiResponse, Profile, ProfileCreate, ProfileUpdate } from "../types";

export const profileApi = {
  getAll: async (): Promise<Profile[]> => {
    const response = await apiClient.get<ApiResponse<Profile[]>>("/profiles");
    return response.data.data;
  },

  getById: async (id: string): Promise<Profile> => {
    const response = await apiClient.get<ApiResponse<Profile>>(`/profiles/${id}`);
    return response.data.data;
  },

  create: async (data: ProfileCreate): Promise<Profile> => {
    const response = await apiClient.post<ApiResponse<Profile>>("/profiles", data);
    return response.data.data;
  },

  update: async (id: string, data: ProfileUpdate): Promise<Profile> => {
    const response = await apiClient.patch<ApiResponse<Profile>>(`/profiles/${id}`, data);
    return response.data.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/profiles/${id}`);
  },

  exportProfile: async (id: string): Promise<Blob> => {
    const response = await apiClient.post(`/profiles/${id}/export`, null, {
      responseType: "blob",
    });
    return response.data;
  },

  importProfile: async (file: File): Promise<Profile> => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post<ApiResponse<Profile>>("/profiles/import", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data.data;
  },
};
