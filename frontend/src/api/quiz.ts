import { apiClient, ApiEnvelope } from "./client";

export type QuestionType = "mcq" | "numerical" | "short_answer";
export type QuizMode = "practice" | "timed_assessment";
export type AssessmentType = "topic_assessment" | "chapter_test" | "comprehensive_exam" | "diagnostic_test";
export type DifficultyLevel = "easy" | "medium" | "hard" | "adaptive";

export interface QuizOption {
  id: string;
  text: string;
}

export interface QuizQuestionPublic {
  id: string;
  question_type: QuestionType;
  prompt: string;
  options?: QuizOption[] | null;
  topic_title?: string;
  difficulty?: DifficultyLevel;
}

export interface QuizResponse {
  id: string;
  profile_id: string;
  roadmap_node_id?: string | null;
  mode: QuizMode;
  total_questions: number;
  time_limit_seconds?: number | null;
  difficulty?: string;
  questions: QuizQuestionPublic[];
}

export interface QuizUserAnswer {
  question_id: string;
  user_answer: string;
}

export interface QuestionResult {
  question_id: string;
  question_type: QuestionType;
  prompt: string;
  user_answer: string;
  correct_answer: string;
  is_correct: boolean;
  score: number;
  error_category?: string;
  feedback: string;
  explanation: string;
  remediation_advice?: string;
}

export interface MasteryNodeUpdate {
  node_id: string;
  node_title: string;
  previous_mastery: number;
  new_mastery: number;
  status: string;
  unlocked: boolean;
}

export interface QuizResultResponse {
  id: string;
  profile_id: string;
  roadmap_node_id?: string | null;
  /** Resolved server-side from the roadmap node. */
  topic_title?: string | null;
  mode: string;
  started_at: string;
  completed_at?: string | null;
  score: number;
  letter_grade?: string;
  total_questions: number;
  correct_count: number;
  time_limit_seconds?: number | null;
  question_results: QuestionResult[];
  mastery_updates?: MasteryNodeUpdate[];
  strengths_recorded?: string[];
  weaknesses_recorded?: string[];
  unlocked_nodes?: string[];
  overall_feedback: string;
  mastery_delta: number;
}

export interface QuizAttemptSummary {
  id: string;
  profile_id: string;
  roadmap_node_id?: string | null;
  /** Resolved server-side from the roadmap node, for labelling history. */
  topic_title?: string | null;
  mode: string;
  started_at: string;
  completed_at?: string | null;
  score?: number | null;
  total_questions: number;
  correct_count?: number | null;
}

export const quizApi = {
  generateQuiz: async (
    profileId: string,
    payload: {
      roadmap_node_id?: string;
      topic_title?: string;
      question_types?: QuestionType[];
      mode?: QuizMode;
      question_count?: number;
      time_limit_seconds?: number;
      difficulty?: DifficultyLevel;
    }
  ): Promise<QuizResponse> => {
    const res = await apiClient.post<ApiEnvelope<QuizResponse>>(
      `/profiles/${profileId}/quiz/generate`,
      payload
    );
    return res.data.data;
  },

  generateAssessment: async (
    profileId: string,
    payload: {
      assessment_type?: AssessmentType;
      roadmap_node_ids?: string[];
      chapter_title?: string;
      topic_titles?: string[];
      difficulty?: DifficultyLevel;
      question_count?: number;
      time_limit_seconds?: number;
    }
  ): Promise<QuizResponse> => {
    const res = await apiClient.post<ApiEnvelope<QuizResponse>>(
      `/profiles/${profileId}/quiz/assessments`,
      payload
    );
    return res.data.data;
  },

  submitQuiz: async (
    profileId: string,
    attemptId: string,
    payload: { answers: QuizUserAnswer[] }
  ): Promise<QuizResultResponse> => {
    const res = await apiClient.post<ApiEnvelope<QuizResultResponse>>(
      `/profiles/${profileId}/quiz/${attemptId}/submit`,
      payload
    );
    return res.data.data;
  },

  getHistory: async (profileId: string): Promise<QuizAttemptSummary[]> => {
    const res = await apiClient.get<ApiEnvelope<QuizAttemptSummary[]>>(
      `/profiles/${profileId}/quiz/history`
    );
    return res.data.data;
  },

  getResults: async (profileId: string, attemptId: string): Promise<QuizResultResponse> => {
    const res = await apiClient.get<ApiEnvelope<QuizResultResponse>>(
      `/profiles/${profileId}/quiz/${attemptId}/results`
    );
    return res.data.data;
  },
};
