import React, { useEffect, useRef, useState } from "react";
import { useProfileStore } from "../stores/profileStore";
import {
  quizApi,
  QuizResponse,
  QuizResultResponse,
  QuizAttemptSummary,
  QuizUserAnswer,
  QuizMode,
} from "../api/quiz";
import { roadmapApi, RoadmapDetail } from "../api/roadmap";
import {
  Award,
  CheckCircle2,
  Clock,
  HelpCircle,
  Sparkles,
  ArrowRight,
  ArrowLeft,
  RotateCcw,
  Check,
  X,
  Layers,
} from "lucide-react";
import { CardSkeleton, Skeleton, EmptyState, ErrorState } from "../components/common/LoadingStates";

export function QuizPage() {
  const { activeProfileId, profiles } = useProfileStore();
  const activeProfile = profiles.find((p) => p.id === activeProfileId);

  // States: 'idle' | 'taking' | 'results'
  const [viewState, setViewState] = useState<"idle" | "taking" | "results">("idle");
  const [activeRoadmap, setActiveRoadmap] = useState<RoadmapDetail | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string>("");
  const [customTopic, setCustomTopic] = useState<string>("");
  const [quizMode, setQuizMode] = useState<QuizMode>("practice");
  const [questionCount, setQuestionCount] = useState<number>(5);
  const [history, setHistory] = useState<QuizAttemptSummary[]>([]);

  // Active Quiz State
  const [activeQuiz, setActiveQuiz] = useState<QuizResponse | null>(null);
  const [userAnswers, setUserAnswers] = useState<Record<string, string>>({});
  const [currentQIndex, setCurrentQIndex] = useState<number>(0);
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  // Results State
  const [quizResult, setQuizResult] = useState<QuizResultResponse | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const submissionStarted = useRef(false);

  // Load roadmap topics and past history
  const loadQuizData = () => {
    if (!activeProfileId) return;
    setHistoryError(null);
    roadmapApi.getActiveRoadmap(activeProfileId)
      .then(setActiveRoadmap)
      .catch((err) => {
        if (err?.response?.status !== 404) setHistoryError("Failed to load quiz topics.");
        setActiveRoadmap(null);
      });
    quizApi.getHistory(activeProfileId)
      .then(setHistory)
      .catch(() => setHistoryError("Failed to load quiz history."));
  };

  useEffect(() => { loadQuizData(); }, [activeProfileId]);

  // Timer countdown for timed assessment
  useEffect(() => {
    if (viewState !== "taking" || timeRemaining === null) return;
    if (timeRemaining <= 0) {
      handleSubmitQuiz();
      return;
    }
    const timer = setInterval(() => {
      setTimeRemaining((prev) => (prev !== null && prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [viewState, timeRemaining]);

  const handleStartQuiz = async () => {
    if (!activeProfileId) return;
    setLoading(true);
    try {
      const timeLimit = quizMode === "timed_assessment" ? questionCount * 60 : undefined;
      const quiz = await quizApi.generateQuiz(activeProfileId, {
        roadmap_node_id: selectedNodeId || undefined,
        topic_title: !selectedNodeId ? customTopic || "Curriculum Concepts" : undefined,
        mode: quizMode,
        question_count: questionCount,
        time_limit_seconds: timeLimit,
      });

      setActiveQuiz(quiz);
      setUserAnswers({});
      setCurrentQIndex(0);
      setTimeRemaining(timeLimit ?? null);
      submissionStarted.current = false;
      setViewState("taking");
    } catch (err: any) {
      setActionError(err?.response?.data?.error?.message || "Failed to generate quiz.");
    } finally {
      setLoading(false);
    }
  };

  const handleAnswerChange = (qId: string, val: string) => {
    setUserAnswers((prev) => ({ ...prev, [qId]: val }));
  };

  const handleSubmitQuiz = async () => {
    if (!activeProfileId || !activeQuiz || submissionStarted.current) return;
    submissionStarted.current = true;
    setLoading(true);
    try {
      const formattedAnswers: QuizUserAnswer[] = activeQuiz.questions.map((q) => ({
        question_id: q.id,
        user_answer: userAnswers[q.id] || "",
      }));

      const res = await quizApi.submitQuiz(activeProfileId, activeQuiz.id, {
        answers: formattedAnswers,
      });

      setQuizResult(res);
      setViewState("results");
      quizApi.getHistory(activeProfileId).then(setHistory).catch(() => setHistoryError("Failed to refresh quiz history."));
    } catch (err: any) {
      submissionStarted.current = false;
      setActionError(err?.response?.data?.error?.message || "Failed submitting quiz.");
    } finally {
      setLoading(false);
    }
  };

  if (!activeProfile) {
    return (
      <div className="p-8 text-center py-20">
        <EmptyState
          icon={Award}
          title="No Active Profile"
          description="Please select or create a learner profile to take diagnostic assessments."
        />
      </div>
    );
  }

  if (historyError && viewState === "idle") {
    return <div className="p-4 sm:p-6 lg:p-8 max-w-5xl mx-auto"><ErrorState message={historyError} onRetry={loadQuizData} /></div>;
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-5xl mx-auto space-y-6">
      {actionError && <ErrorState message={actionError} actionLabel="Dismiss" onRetry={() => setActionError(null)} />}
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-primary-container/30 text-primary border border-glass-border uppercase tracking-widest">
            Cognitive Diagnostics
          </span>
        </div>
        <h1 className="font-editorial text-3xl sm:text-4xl text-on-surface mt-1.5 tracking-tight">
          Quiz & Assessment Engine
        </h1>
        <p className="text-xs sm:text-sm text-on-surface-variant mt-1 font-sans">
          Adaptive testing, timed drills, and automated mastery scoring across conceptual milestones.
        </p>
      </div>

      {/* VIEW: IDLE / CONFIGURATION */}
      {viewState === "idle" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Generator Form */}
          <div className="lg:col-span-2 glass-panel p-6 rounded-2xl border border-glass-border space-y-5 shadow-[0_4px_30px_rgba(0,0,0,0.1)]">
            <h2 className="font-editorial text-2xl text-on-surface">
              Configure Diagnostic Test
            </h2>

            <div className="space-y-4 font-sans text-xs">
              {/* Topic Selector */}
              <div>
                <label className="block text-on-surface-variant mb-1 font-semibold">
                  Select Concept or Roadmap Node
                </label>
                {activeRoadmap?.nodes && activeRoadmap.nodes.length > 0 ? (
                  <select
                    value={selectedNodeId}
                    onChange={(e) => setSelectedNodeId(e.target.value)}
                    className="w-full px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden focus:border-primary"
                  >
                    <option value="">-- Custom Topic --</option>
                    {activeRoadmap.nodes.map((n) => (
                      <option key={n.id} value={n.id} className="bg-surface text-on-surface">
                        {n.title} (Mastery: {Math.round(n.mastery_score * 100)}%)
                      </option>
                    ))}
                  </select>
                ) : null}

                {!selectedNodeId && (
                  <input
                    type="text"
                    placeholder="Enter custom topic (e.g. Organic Reaction Mechanisms)..."
                    value={customTopic}
                    onChange={(e) => setCustomTopic(e.target.value)}
                    className="w-full mt-2 px-3 py-2 bg-surface-container/50 border border-glass-border rounded-lg text-on-surface focus:outline-hidden focus:border-primary"
                  />
                )}
              </div>

              {/* Assessment Mode */}
              <div>
                <label className="block text-on-surface-variant mb-1 font-semibold">Assessment Mode</label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { id: "practice", label: "Practice Drill", desc: "Untimed, immediate mastery scoring" },
                    { id: "timed_assessment", label: "Timed Drill", desc: "1 min per question timer" },
                  ].map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => setQuizMode(m.id as QuizMode)}
                      className={`p-3 rounded-xl border text-left transition ${
                        quizMode === m.id
                          ? "bg-surface-container/70 border-primary shadow-[0_0_8px_rgba(160,240,237,0.2)] luminous-active"
                          : "bg-surface-container/30 border-glass-border hover:bg-surface-container/50 text-on-surface-variant"
                      }`}
                    >
                      <div className="font-semibold text-xs text-on-surface">{m.label}</div>
                      <div className="text-[10px] text-on-surface-variant mt-0.5">{m.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Question Count */}
              <div>
                <label className="block text-on-surface-variant mb-1 font-semibold">
                  Number of Questions: <span className="text-primary font-mono">{questionCount}</span>
                </label>
                <input
                  type="range"
                  min="3"
                  max="10"
                  value={questionCount}
                  onChange={(e) => setQuestionCount(parseInt(e.target.value))}
                  className="w-full accent-primary"
                />
              </div>
            </div>

            <button
              onClick={handleStartQuiz}
              disabled={loading || (!selectedNodeId && !customTopic.trim())}
              className="w-full py-3 bg-primary hover:opacity-90 disabled:opacity-40 text-on-primary text-xs font-semibold rounded-xl shadow-[0_0_15px_rgba(160,240,237,0.3)] transition flex items-center justify-center gap-2"
            >
              <Sparkles className="w-4 h-4" />
              {loading ? "Synthesizing Assessment..." : "Launch Quiz Session"}
            </button>
          </div>

          {/* Past Quiz Attempts */}
          <div className="glass-panel p-6 rounded-2xl border border-glass-border space-y-4">
            <h3 className="font-editorial text-2xl text-on-surface">Recent Attempts</h3>
            {history.length > 0 ? (
              <div className="space-y-2.5 max-h-96 overflow-y-auto">
                {history.slice(0, 6).map((item) => (
                  <div
                    key={item.id}
                    className="p-3 rounded-xl bg-surface-container/30 border border-glass-border flex justify-between items-center gap-3"
                  >
                    {/* Labelled by subject and date. A slice of the attempt
                        UUID told the learner nothing about what was tested. */}
                    <div className="min-w-0">
                      <h4 className="text-xs font-semibold text-on-surface truncate">
                        {item.topic_title || "General assessment"}
                      </h4>
                      <span className="text-[10px] text-on-surface-variant font-mono capitalize">
                        {new Date(item.completed_at ?? item.started_at).toLocaleDateString(undefined, {
                          day: "numeric",
                          month: "short",
                        })}{" "}
                        • {item.mode} • {item.correct_count ?? 0}/{item.total_questions} correct
                      </span>
                    </div>
                    <span className="font-editorial text-lg text-primary shrink-0">
                      {Math.round((item.score ?? 0) * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-on-surface-variant font-sans">
                No past quiz records yet.
              </div>
            )}
          </div>
        </div>
      )}

      {/* VIEW: TAKING QUIZ */}
      {viewState === "taking" && activeQuiz && (
        <div className="glass-panel p-6 sm:p-8 rounded-2xl border border-glass-border space-y-6 shadow-2xl">
          <div className="flex justify-between items-center pb-4 border-b border-glass-border">
            <div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-primary-container/40 text-primary uppercase">
                {activeQuiz.mode}
              </span>
              <h2 className="font-editorial text-2xl sm:text-3xl text-on-surface mt-1">
                Diagnostic Assessment
              </h2>
            </div>
            {timeRemaining !== null && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-mono">
                <Clock className="w-4 h-4" />
                <span>
                  {Math.floor(timeRemaining / 60)}:{(timeRemaining % 60).toString().padStart(2, "0")}
                </span>
              </div>
            )}
          </div>

          {/* Current Question */}
          {(() => {
            const q = activeQuiz.questions[currentQIndex];
            if (!q) return null;
            return (
              <div className="space-y-4 font-sans">
                <div className="flex justify-between items-center text-xs text-on-surface-variant font-mono">
                  <span>Question {currentQIndex + 1} of {activeQuiz.questions.length}</span>
                  <span className="capitalize">{q.question_type}</span>
                </div>

                <p className="text-sm sm:text-base font-semibold text-on-surface leading-relaxed">
                  {q.prompt}
                </p>

                {/* Multiple Choice Options */}
                {q.question_type === "mcq" && q.options && (
                  <div className="space-y-2 pt-2">
                    {q.options.map((opt) => (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => handleAnswerChange(q.id, opt.id)}
                        className={`w-full p-3.5 rounded-xl border text-left text-xs sm:text-sm font-medium transition flex items-center gap-3 ${
                          userAnswers[q.id] === opt.id
                            ? "bg-surface-container/70 border-primary text-primary shadow-[0_0_8px_rgba(160,240,237,0.2)]"
                            : "bg-surface-container/30 border-glass-border text-on-surface hover:bg-surface-container/60"
                        }`}
                      >
                        <span className="w-6 h-6 rounded-md bg-surface-container-high border border-glass-border flex items-center justify-center font-mono text-xs shrink-0">
                          {opt.id}
                        </span>
                        <span>{opt.text}</span>
                      </button>
                    ))}
                  </div>
                )}

                {/* Free Text / Numerical */}
                {q.question_type !== "mcq" && (
                  <textarea
                    rows={3}
                    placeholder="Type your solution or answer..."
                    value={userAnswers[q.id] || ""}
                    onChange={(e) => handleAnswerChange(q.id, e.target.value)}
                    className="w-full p-3 bg-surface-container/50 border border-glass-border rounded-xl text-xs sm:text-sm text-on-surface focus:outline-hidden focus:border-primary"
                  />
                )}
              </div>
            );
          })()}

          {/* Navigation Controls */}
          <div className="flex justify-between items-center pt-4 border-t border-glass-border">
            <button
              onClick={() => setCurrentQIndex((prev) => Math.max(0, prev - 1))}
              disabled={currentQIndex === 0}
              className="px-4 py-2 rounded-lg bg-surface-container/50 hover:bg-surface-container-high disabled:opacity-30 text-xs font-semibold text-on-surface border border-glass-border transition"
            >
              Previous
            </button>

            {currentQIndex < activeQuiz.questions.length - 1 ? (
              <button
                onClick={() => setCurrentQIndex((prev) => prev + 1)}
                className="px-4 py-2 rounded-lg bg-primary hover:opacity-90 text-xs font-semibold text-on-primary shadow-sm transition"
              >
                Next Question
              </button>
            ) : (
              <button
                onClick={handleSubmitQuiz}
                disabled={loading}
                className="px-5 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-xs font-semibold text-white shadow-[0_0_12px_rgba(52,211,153,0.3)] transition"
              >
                {loading ? "Grading..." : "Submit Assessment"}
              </button>
            )}
          </div>
        </div>
      )}

      {/* VIEW: RESULTS */}
      {viewState === "results" && quizResult && (
        <div className="glass-panel p-6 sm:p-8 rounded-2xl border border-glass-border space-y-6 shadow-2xl">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-4 border-b border-glass-border">
            <div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 uppercase">
                Diagnostic Complete
              </span>
              <h2 className="font-editorial text-3xl sm:text-4xl text-on-surface mt-1">
                Score: {Math.round(quizResult.score * 100)}%
              </h2>
              <p className="text-xs text-on-surface-variant font-sans mt-0.5">
                {quizResult.correct_count} of {quizResult.total_questions} questions correct • Topic Mastery Updated
              </p>
            </div>

            <button
              onClick={() => setViewState("idle")}
              className="px-4 py-2 bg-primary hover:opacity-90 text-on-primary text-xs font-semibold rounded-lg shadow-sm transition flex items-center gap-1.5"
            >
              <RotateCcw className="w-3.5 h-3.5" /> Back to Dashboard
            </button>
          </div>

          {/* Question Breakdown */}
          <div className="space-y-4 font-sans text-xs">
            {quizResult.question_results.map((ev, i) => (
              <div
                key={i}
                className={`p-4 rounded-xl border ${
                  ev.is_correct
                    ? "bg-emerald-500/10 border-emerald-500/20"
                    : "bg-rose-500/10 border-rose-500/20"
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-semibold text-on-surface">Question {i + 1}</span>
                  <span
                    className={`font-semibold uppercase text-[10px] ${
                      ev.is_correct ? "text-emerald-400" : "text-rose-400"
                    }`}
                  >
                    {ev.is_correct ? "Correct" : "Incorrect"}
                  </span>
                </div>
                <p className="text-on-surface-variant mb-2">{ev.explanation || ev.feedback}</p>
                <div className="text-[11px] text-on-surface-variant/80">
                  <span className="font-semibold">Correct Answer:</span> {ev.correct_answer}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
