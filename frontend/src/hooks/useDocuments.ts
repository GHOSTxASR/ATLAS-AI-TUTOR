import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { documentsApi } from "../api/documents";
import { Document } from "../types";

export function extractErrorMessage(err: unknown, fallback: string): string {
  const response = (err as { response?: { data?: { error?: { message?: string } } } })?.response;
  return response?.data?.error?.message ?? fallback;
}

const PROCESSING_STATUSES = new Set([
  "pending",
  "extracting",
  "pending_ocr",
  "chunking",
  "queuing",
  "indexing",
]);

export function useDocuments(profileId: string | null) {
  return useQuery({
    queryKey: ["documents", profileId],
    queryFn: () => documentsApi.getAll(profileId as string),
    enabled: Boolean(profileId),
    // Poll while any document is still mid-processing so status updates show
    // up without a manual refresh (matters once ingestion becomes async).
    refetchInterval: (query) => {
      const documents = query.state.data as Document[] | undefined;
      const stillProcessing = documents?.some((doc) => PROCESSING_STATUSES.has(doc.status));
      return stillProcessing ? 2000 : false;
    },
  });
}

export function useUploadDocument(profileId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ file, isSyllabus }: { file: File; isSyllabus?: boolean }) => {
      if (!profileId) throw new Error("No active profile selected.");
      try {
        return await documentsApi.upload(profileId, file, isSyllabus);
      } catch (err) {
        throw new Error(extractErrorMessage(err, "Failed to upload document."));
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", profileId] });
    },
  });
}

export function useDeleteDocument(profileId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (documentId: string) => {
      if (!profileId) throw new Error("No active profile selected.");
      try {
        await documentsApi.delete(profileId, documentId);
      } catch (err) {
        throw new Error(extractErrorMessage(err, "Failed to delete document."));
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", profileId] });
    },
  });
}

export function useReprocessDocument(profileId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (documentId: string) => {
      if (!profileId) throw new Error("No active profile selected.");
      try {
        return await documentsApi.reprocess(profileId, documentId);
      } catch (err) {
        throw new Error(extractErrorMessage(err, "Failed to reprocess document."));
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", profileId] });
    },
  });
}
