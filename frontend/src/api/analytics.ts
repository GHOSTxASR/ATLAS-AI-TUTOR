import { apiClient, ApiEnvelope } from "./client";

export interface AnalyticsEvent {
  id: string;
  profile_id: string;
  event_type: string;
  entity_type: string;
  entity_id: string | null;
  value: number | null;
  metadata_json: string | null;
  occurred_at: string;
}

export interface ChapterProgressItem {
  chapter_title: string;
  total_topics: number;
  completed_topics: number;
  completion_percentage: number;
  average_mastery: number;
}

export interface StudyTimeBreakdown {
  roadmap_minutes: number;
  chat_minutes: number;
  quiz_minutes: number;
  notes_minutes: number;
  total_minutes: number;
}

export interface AnalyticsOverview {
  completion_percentage: number;
  total_topics: number;
  completed_topics: number;
  in_progress_topics: number;
  not_started_topics: number;
  average_mastery: number;
  total_study_minutes: number;
  active_streak_days: number;
  total_sessions: number;
  total_documents: number;
  total_notes: number;
  total_quizzes_taken: number;
  average_quiz_score: number;
  study_time_breakdown: StudyTimeBreakdown;
  chapter_progress: ChapterProgressItem[];
}

export interface ActivityHeatmapItem {
  date: string;
  minutes: number;
  events_count: number;
}

export interface MasteryTierTopic {
  id: string;
  title: string;
  mastery_score: number;
  status: string;
}

export interface MasteryDistribution {
  mastered_count: number;
  proficient_count: number;
  needs_practice_count: number;
  unstarted_count: number;
  mastered_topics: MasteryTierTopic[];
  proficient_topics: MasteryTierTopic[];
  needs_practice_topics: MasteryTierTopic[];
  unstarted_topics: MasteryTierTopic[];
}

export interface LearningVelocityPoint {
  date: string;
  topics_completed: number;
  study_minutes: number;
}

export interface WeaknessConcept {
  id?: string;
  title: string;
  subject?: string;
  source: string;
  mastery_score?: number;
  reason: string;
}

export const analyticsApi = {
  getOverview: async (profileId: string): Promise<AnalyticsOverview> => {
    const res = await apiClient.get<ApiEnvelope<AnalyticsOverview>>(
      `/profiles/${profileId}/analytics/overview`
    );
    return res.data.data;
  },

  getHeatmap: async (
    profileId: string,
    days: number = 30
  ): Promise<ActivityHeatmapItem[]> => {
    const res = await apiClient.get<ApiEnvelope<ActivityHeatmapItem[]>>(
      `/profiles/${profileId}/analytics/heatmap`,
      { params: { days } }
    );
    return res.data.data;
  },

  getMastery: async (profileId: string): Promise<MasteryDistribution> => {
    const res = await apiClient.get<ApiEnvelope<MasteryDistribution>>(
      `/profiles/${profileId}/analytics/mastery`
    );
    return res.data.data;
  },

  getVelocity: async (
    profileId: string,
    days: number = 14
  ): Promise<LearningVelocityPoint[]> => {
    const res = await apiClient.get<ApiEnvelope<LearningVelocityPoint[]>>(
      `/profiles/${profileId}/analytics/velocity`,
      { params: { days } }
    );
    return res.data.data;
  },

  getWeaknesses: async (profileId: string): Promise<WeaknessConcept[]> => {
    const res = await apiClient.get<ApiEnvelope<WeaknessConcept[]>>(
      `/profiles/${profileId}/analytics/weaknesses`
    );
    return res.data.data;
  },

  logEvent: async (
    profileId: string,
    payload: {
      event_type: string;
      entity_type?: string;
      entity_id?: string;
      value?: number;
      metadata_json?: string;
    }
  ): Promise<AnalyticsEvent> => {
    const res = await apiClient.post<ApiEnvelope<AnalyticsEvent>>(
      `/profiles/${profileId}/analytics/events`,
      payload
    );
    return res.data.data;
  },
};
