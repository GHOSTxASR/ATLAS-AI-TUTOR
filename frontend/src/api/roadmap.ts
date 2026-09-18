import { apiClient, ApiEnvelope } from "./client";

export interface RoadmapNode {
  id: string;
  roadmap_id: string;
  profile_id: string;
  title: string;
  description?: string | null;
  node_type: "subject" | "chapter" | "topic" | "bridge";
  status: "not_started" | "in_progress" | "completed" | "skipped" | "flagged";
  parent_id?: string | null;
  order_index: number;
  mastery_score: number;
  time_spent_minutes: number;
  ai_generated: boolean;
  completed_at?: string | null;
  unlocked: boolean;
}

export interface RoadmapEdge {
  id: string;
  roadmap_id: string;
  from_node_id: string;
  to_node_id: string;
  edge_type: "sequential" | "prerequisite" | "bridge";
}

export interface RoadmapProgress {
  total_nodes: number;
  completed_nodes: number;
  in_progress_nodes: number;
  completion_percentage: number;
  average_mastery: number;
}

export interface RoadmapDetail {
  id: string;
  profile_id: string;
  title: string;
  mode: "strict" | "adaptive" | "hybrid";
  version: number;
  is_active: boolean;
  source_document_id?: string | null;
  created_at: string;
  nodes: RoadmapNode[];
  edges: RoadmapEdge[];
  progress?: RoadmapProgress | null;
}

export interface RoadmapSummary {
  id: string;
  profile_id: string;
  title: string;
  mode: string;
  version: number;
  is_active: boolean;
  source_document_id?: string | null;
  created_at: string;
  node_count: number;
}

export const roadmapApi = {
  listRoadmaps: async (profileId: string): Promise<RoadmapSummary[]> => {
    const res = await apiClient.get<ApiEnvelope<RoadmapSummary[]>>(
      `/profiles/${profileId}/roadmaps`
    );
    return res.data.data;
  },

  getActiveRoadmap: async (profileId: string): Promise<RoadmapDetail> => {
    const res = await apiClient.get<ApiEnvelope<RoadmapDetail>>(
      `/profiles/${profileId}/roadmaps/active`
    );
    return res.data.data;
  },

  getRoadmap: async (profileId: string, roadmapId: string): Promise<RoadmapDetail> => {
    const res = await apiClient.get<ApiEnvelope<RoadmapDetail>>(
      `/profiles/${profileId}/roadmaps/${roadmapId}`
    );
    return res.data.data;
  },

  generateRoadmap: async (
    profileId: string,
    payload: {
      document_id?: string;
      /** Course materials to write a curriculum from, when no syllabus exists. */
      document_ids?: string[];
      mode?: "strict" | "adaptive" | "hybrid";
      title?: string;
      syllabus_text?: string;
    }
  ): Promise<RoadmapDetail> => {
    const res = await apiClient.post<ApiEnvelope<RoadmapDetail>>(
      `/profiles/${profileId}/roadmaps`,
      payload
    );
    return res.data.data;
  },

  updateNodeStatus: async (
    profileId: string,
    roadmapId: string,
    nodeId: string,
    payload: {
      status?: "not_started" | "in_progress" | "completed" | "skipped" | "flagged";
      mastery_score?: number;
      time_spent_minutes?: number;
    }
  ): Promise<RoadmapNode> => {
    const res = await apiClient.patch<ApiEnvelope<RoadmapNode>>(
      `/profiles/${profileId}/roadmaps/${roadmapId}/nodes/${nodeId}`,
      payload
    );
    return res.data.data;
  },

  regenerateRoadmap: async (
    profileId: string,
    roadmapId: string
  ): Promise<RoadmapDetail> => {
    const res = await apiClient.post<ApiEnvelope<RoadmapDetail>>(
      `/profiles/${profileId}/roadmaps/${roadmapId}/regenerate`
    );
    return res.data.data;
  },
};
