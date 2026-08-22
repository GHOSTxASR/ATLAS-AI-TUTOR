import { apiClient } from "./client";
import { ApiResponse, Document, DocumentStatusInfo } from "../types";

export const documentsApi = {
  getAll: async (profileId: string): Promise<Document[]> => {
    const response = await apiClient.get<ApiResponse<Document[]>>(`/profiles/${profileId}/documents`);
    return response.data.data;
  },

  getById: async (profileId: string, documentId: string): Promise<Document> => {
    const response = await apiClient.get<ApiResponse<Document>>(
      `/profiles/${profileId}/documents/${documentId}`
    );
    return response.data.data;
  },

  getStatus: async (profileId: string, documentId: string): Promise<DocumentStatusInfo> => {
    const response = await apiClient.get<ApiResponse<DocumentStatusInfo>>(
      `/profiles/${profileId}/documents/${documentId}/status`
    );
    return response.data.data;
  },

  upload: async (
    profileId: string,
    file: File,
    isSyllabus = false,
    onProgress?: (percent: number) => void
  ): Promise<Document> => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("is_syllabus", String(isSyllabus));

    const response = await apiClient.post<ApiResponse<Document>>(
      `/profiles/${profileId}/documents`,
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (event) => {
          if (onProgress && event.total) {
            onProgress(Math.round((event.loaded / event.total) * 100));
          }
        },
      }
    );
    return response.data.data;
  },

  reprocess: async (profileId: string, documentId: string): Promise<Document> => {
    const response = await apiClient.post<ApiResponse<Document>>(
      `/profiles/${profileId}/documents/${documentId}/reprocess`
    );
    return response.data.data;
  },

  delete: async (profileId: string, documentId: string): Promise<void> => {
    await apiClient.delete(`/profiles/${profileId}/documents/${documentId}`);
  },
};
