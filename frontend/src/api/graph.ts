import { apiClient, ApiEnvelope } from "./client";

export type GraphNodeType = "concept" | "chapter" | "subject" | "document" | "note" | "quiz";
export type GraphEdgeType = "prerequisite_of" | "related_to" | "taught_in" | "referenced_by" | "learned_from" | "tested_by";

export interface GraphNode {
  id: string;
  label: string;
  type: GraphNodeType;
  profile_id: string;
  description?: string;
  mastery_score: number;
  mention_count: number;
  first_seen: string;
  last_seen: string;
  roadmap_node_id?: string | null;
  document_ids: string[];
  chat_session_ids: string[];
}

export interface GraphEdge {
  source: string;
  target: string;
  type: GraphEdgeType;
  weight: number;
  created_at: string;
}

export interface GraphStats {
  total_nodes: number;
  total_edges: number;
  concepts_count: number;
  documents_count: number;
  average_mastery: number;
}

export interface GraphDataResponse {
  nodes: GraphNode[];
  links: GraphEdge[];
  directed: boolean;
  multigraph: boolean;
  stats?: GraphStats;
}

export interface GraphPathResponse {
  source_id: string;
  target_id: string;
  path_found: boolean;
  path: GraphNode[];
  length: number;
}

export const graphApi = {
  getGraph: async (profileId: string): Promise<GraphDataResponse> => {
    const res = await apiClient.get<ApiEnvelope<GraphDataResponse>>(
      `/profiles/${profileId}/graph`
    );
    return res.data.data;
  },

  createNode: async (
    profileId: string,
    payload: {
      label: string;
      type?: GraphNodeType;
      description?: string;
      mastery_score?: number;
    }
  ): Promise<GraphNode> => {
    const res = await apiClient.post<ApiEnvelope<GraphNode>>(
      `/profiles/${profileId}/graph/nodes`,
      payload
    );
    return res.data.data;
  },

  updateNode: async (
    profileId: string,
    nodeId: string,
    payload: {
      label?: string;
      description?: string;
      mastery_score?: number;
      mention_count?: number;
    }
  ): Promise<GraphNode> => {
    const res = await apiClient.patch<ApiEnvelope<GraphNode>>(
      `/profiles/${profileId}/graph/nodes/${nodeId}`,
      payload
    );
    return res.data.data;
  },

  deleteNode: async (profileId: string, nodeId: string): Promise<boolean> => {
    const res = await apiClient.delete<ApiEnvelope<{ deleted: boolean }>>(
      `/profiles/${profileId}/graph/nodes/${nodeId}`
    );
    return res.data.data.deleted;
  },

  createEdge: async (
    profileId: string,
    payload: {
      source: string;
      target: string;
      type?: GraphEdgeType;
      weight?: number;
    }
  ): Promise<GraphEdge> => {
    const res = await apiClient.post<ApiEnvelope<GraphEdge>>(
      `/profiles/${profileId}/graph/edges`,
      payload
    );
    return res.data.data;
  },

  deleteEdge: async (profileId: string, source: string, target: string): Promise<boolean> => {
    const res = await apiClient.delete<ApiEnvelope<{ deleted: boolean }>>(
      `/profiles/${profileId}/graph/edges?source=${source}&target=${target}`
    );
    return res.data.data.deleted;
  },

  enrichGraph: async (
    profileId: string,
    payload: {
      /** Read the text from a document already uploaded. */
      document_id?: string;
      /** Pasted text, for content that is not in the library. */
      text?: string;
      source_type?: string;
      source_id?: string;
      source_label?: string;
    }
  ): Promise<GraphDataResponse> => {
    const res = await apiClient.post<ApiEnvelope<GraphDataResponse>>(
      `/profiles/${profileId}/graph/enrich`,
      payload
    );
    return res.data.data;
  },

  searchNodes: async (profileId: string, query: string): Promise<GraphNode[]> => {
    const res = await apiClient.get<ApiEnvelope<GraphNode[]>>(
      `/profiles/${profileId}/graph/search?q=${encodeURIComponent(query)}`
    );
    return res.data.data;
  },

  findPath: async (profileId: string, sourceId: string, targetId: string): Promise<GraphPathResponse> => {
    const res = await apiClient.get<ApiEnvelope<GraphPathResponse>>(
      `/profiles/${profileId}/graph/path?source_id=${sourceId}&target_id=${targetId}`
    );
    return res.data.data;
  },
};
