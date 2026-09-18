import React, { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  Loader2,
  MessageSquare,
  PenLine,
  Plus,
  Search,
  Send,
  Trash2,
  User,
  GraduationCap,
  Zap,
  FileText,
  Globe,
  Layers,
  Brain,
  Compass,
  Share2,
  BookOpen,
  X,
  Menu,
} from "lucide-react";
import { useChatStore } from "../stores/chatStore";
import { useProfileStore } from "../stores/profileStore";
import { chatApi, LearningMode, UnifiedLearningContext } from "../api/chat";
import { StudyIntent, openingPromptFor } from "../hooks/useOpenTutor";
import { EmptyState, Skeleton } from "../components/common/LoadingStates";
import { MarkdownContent } from "../components/common/MarkdownContent";
import { CitationList } from "../components/chat/CitationList";
import { AtlasBlob, ThinkingIndicator } from "../components/chat/ThinkingIndicator";
import atlasMark from "../assets/atlas-mark.png";

export function ChatPage() {
  const { activeProfileId } = useProfileStore();
  const {
    sessions,
    activeSession,
    isStreaming,
    wsReady,
    streamingContent,
    streamingCitations,
    error,
    searchQuery,
    setSearchQuery,
    loadSessions,
    loadSession,
    createSession,
    updateSession,
    autotitleSession,
    deleteSession,
    sendStreamingMessage,
    clearActiveSession,
  } = useChatStore();

  const [messageInput, setMessageInput] = useState("");
  const [selectedMode, setSelectedMode] = useState<LearningMode>("teaching");
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [showContextPanel, setShowContextPanel] = useState<boolean>(false);
  const [showSessionDrawer, setShowSessionDrawer] = useState<boolean>(false);
  const [unifiedContext, setUnifiedContext] = useState<UnifiedLearningContext | null>(null);
  const [loadingContext, setLoadingContext] = useState<boolean>(false);
  const messagesPaneRef = useRef<HTMLDivElement>(null);

  const navigate = useNavigate();
  const { sessionId: urlSessionId } = useParams<{ sessionId: string }>();
  const [searchParams] = useSearchParams();
  const targetSessionId = urlSessionId || searchParams.get("session_id");
  const topic = searchParams.get("topic");
  const location = useLocation();
  const studyTopic = (location.state as StudyIntent | null)?.studyTopic;

  // A "?topic=" arrival with no session still just pre-fills the box: there is
  // no thread to send into yet.
  useEffect(() => {
    if (topic) {
      setMessageInput(topic);
    }
  }, [topic]);

  // Opened from the roadmap or the graph to study something: ask the first
  // question on the learner's behalf, so the tutor actually starts.
  //
  // Three separate guards stop it repeating, because each covers a different
  // way it could fire twice:
  //   - the ref: re-renders while the answer streams in
  //   - the empty-thread check: returning to a topic already discussed
  //   - router state, which a reload discards: refreshing mid-answer
  //
  // It also waits for the socket: the session is in the store before the
  // connection is usable, and sending into a half-open socket fails
  // silently while still counting as the one attempt.
  const autoStartedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!studyTopic || !activeProfileId || !activeSession || isStreaming) return;
    if (!wsReady) return;
    if (autoStartedFor.current === activeSession.id) return;
    if ((activeSession.messages ?? []).length > 0) return;

    autoStartedFor.current = activeSession.id;
    sendStreamingMessage(
      activeProfileId,
      activeSession.id,
      openingPromptFor(studyTopic),
      {
        mode: selectedMode,
        roadmapNodeId: activeSession.roadmap_node_id ?? undefined,
      },
    );
  }, [
    studyTopic,
    activeProfileId,
    activeSession,
    isStreaming,
    wsReady,
    selectedMode,
    sendStreamingMessage,
  ]);

  useEffect(() => {
    if (activeProfileId) {
      loadSessions(activeProfileId);
      if (targetSessionId) {
        loadSession(activeProfileId, targetSessionId);
      } else {
        clearActiveSession();
      }
    }
  }, [activeProfileId, targetSessionId, loadSession, clearActiveSession, loadSessions]);

  // Fetch Unified Context when opening Context Panel
  useEffect(() => {
    if (activeProfileId && showContextPanel) {
      setLoadingContext(true);
      chatApi
        .getUnifiedContext(activeProfileId, {
          q: messageInput || "Current study session",
          mode: selectedMode,
        })
        .then((data) => setUnifiedContext(data))
        .catch((err) => console.error("Failed loading unified context:", err))
        .finally(() => setLoadingContext(false));
    }
    // messageInput is read as a snapshot of whatever is typed when the panel
    // opens; depending on it would refetch the whole context on every keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeProfileId, showContextPanel, selectedMode]);

  // Reload sessions when search changes (debounced)
  useEffect(() => {
    if (activeProfileId) {
      const timeout = setTimeout(() => {
        loadSessions(activeProfileId);
      }, 250);
      return () => clearTimeout(timeout);
    }
  }, [searchQuery, activeProfileId, loadSessions]);

  // Name a session once its first exchange is on screen.
  // Fires on the streaming->idle edge rather than inside the send path: the
  // reply is what the user is waiting for, and titling should not sit in front
  // of it. Guarded on the default title so a name the user typed is never
  // overwritten, and on having a reply so the title reflects a real exchange.
  const wasStreamingRef = useRef(false);
  useEffect(() => {
    const justFinished = wasStreamingRef.current && !isStreaming;
    wasStreamingRef.current = isStreaming;
    if (!justFinished || !activeProfileId || !activeSession) return;

    const isDefaultTitle = /^(chat|new session)\s*(\(.*\))?$/i.test(
      (activeSession.title || "").trim()
    );
    const hasReply = (activeSession.messages ?? []).some((m) => m.role === "assistant");
    if (isDefaultTitle && hasReply) {
      autotitleSession(activeProfileId, activeSession.id);
    }
  }, [isStreaming, activeProfileId, activeSession, autotitleSession]);

  // Keep the thread pinned to the newest message.
  //
  // Scrolls the pane itself rather than calling scrollIntoView on an anchor
  // inside it. scrollIntoView moves *every* scrollable ancestor to bring the
  // element into view -- including ancestors with overflow-hidden, which are
  // still scrollable programmatically, and the document itself. So following
  // the conversation could carry the whole chat column up with it, leaving the
  // composer at the top of the screen and the header out of sight.
  //
  // Instant while tokens are arriving: a smooth scroll started on every chunk
  // means several animations a second, each interrupting the last.
  useEffect(() => {
    const pane = messagesPaneRef.current;
    if (!pane) return;
    pane.scrollTo({
      top: pane.scrollHeight,
      behavior: isStreaming ? "auto" : "smooth",
    });
  }, [activeSession?.messages, streamingContent, isStreaming]);

  const handleCreateChat = () => {
    if (activeProfileId) {
      createSession(activeProfileId, { title: "New Session" });
      setShowSessionDrawer(false);
    }
  };

  const handleSelectChat = (sessionId: string) => {
    if (activeProfileId && activeSession?.id !== sessionId) {
      navigate(`/chat/${sessionId}`);
      setShowSessionDrawer(false);
    }
  };

  const handleDeleteChat = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (activeProfileId) {
      deleteSession(activeProfileId, sessionId);
    }
  };

  const handleRenameSubmit = (
    e: React.KeyboardEvent | React.FocusEvent,
    sessionId: string
  ) => {
    if (e.type === "keydown" && (e as React.KeyboardEvent).key !== "Enter") {
      return;
    }
    if (activeProfileId && editingTitle.trim()) {
      updateSession(activeProfileId, sessionId, { title: editingTitle.trim() });
    }
    setEditingSessionId(null);
  };

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!messageInput.trim() || !activeProfileId || !activeSession || isStreaming) {
      return;
    }
    // Still connecting: keep what was typed rather than clearing it into a
    // socket that cannot carry it.
    if (!wsReady) return;
    const query = messageInput;
    setMessageInput("");
    sendStreamingMessage(activeProfileId, activeSession.id, query, {
      mode: selectedMode,
      roadmapNodeId: activeSession.roadmap_node_id ?? undefined,
    });
  };

  if (!activeProfileId) {
    return (
      <div className="p-8 max-w-xl mx-auto text-center py-20">
        <EmptyState
          icon={Brain}
          title="Select a Learner Profile"
          description="Create or select a profile to initialize your AI Tutor workstation."
          actionLabel="Go to Setup"
          onAction={() => navigate("/setup")}
        />
      </div>
    );
  }

  const modesConfig = [
    { id: "teaching", label: "Teaching", icon: GraduationCap, desc: "Socratic First-Principles" },
    { id: "revision", label: "Revision", icon: Zap, desc: "Active Recall & Drills" },
    { id: "summary", label: "Summary", icon: FileText, desc: "Structured Markdown Takeaways" },
    { id: "general_knowledge", label: "General", icon: Globe, desc: "Broad Concept Synthesis" },
  ];

  return (
    <div className="page-own-layout flex-1 min-h-0 flex glass-panel border border-glass-border overflow-hidden">
      {/* Session Drawer (Desktop sidebar + Mobile overlay) */}
      <div
        className={`w-72 glass-panel-deep border-r border-glass-border flex flex-col shrink-0 transition-transform duration-300 z-20 ${
          showSessionDrawer
            ? "fixed inset-y-0 left-0 translate-x-0 bg-surface/90 dark:bg-[#131314]/95 backdrop-blur-xl"
            : "hidden md:flex"
        }`}
      >
        {/* Session Drawer Header */}
        <div className="p-3.5 border-b border-glass-border space-y-2.5">
          <div className="flex items-center justify-between">
            <h3 className="font-editorial text-xl text-on-surface">Dialogues</h3>
            <button
              onClick={handleCreateChat}
              className="atlas-btn atlas-btn-primary"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>New</span>
            </button>
          </div>

          {/* Search sessions */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant" />
            <input
              type="text"
              placeholder="Search dialogues..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 bg-surface-container/40 border border-glass-border text-xs text-on-surface placeholder:text-on-surface-variant/60 focus:outline-hidden focus:border-primary transition"
            />
          </div>
        </div>

        {/* Sessions List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {sessions.map((session) => (
            <div
              key={session.id}
              onClick={() => handleSelectChat(session.id)}
              className={`group flex items-center justify-between p-2.5 text-xs cursor-pointer transition duration-150 border ${
                activeSession?.id === session.id
                  ? "bg-surface-container/60 text-luminous-highlight border-glass-border shadow-[0_0_10px_rgba(var(--accent-rgb),0.1)] luminous-active"
                  : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container/30 border-transparent"
              }`}
            >
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <MessageSquare className="w-3.5 h-3.5 shrink-0" />
                {editingSessionId === session.id ? (
                  <input
                    type="text"
                    value={editingTitle}
                    onChange={(e) => setEditingTitle(e.target.value)}
                    onBlur={(e) => handleRenameSubmit(e, session.id)}
                    onKeyDown={(e) => handleRenameSubmit(e, session.id)}
                    autoFocus
                    className="w-full bg-surface-container text-on-surface px-1.5 py-0.5 rounded text-xs focus:outline-hidden border border-primary"
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <span className="truncate font-sans text-xs">{session.title}</span>
                )}
              </div>

              <div className="flex items-center opacity-0 group-hover:opacity-100 transition-opacity gap-1">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditingSessionId(session.id);
                    setEditingTitle(session.title);
                  }}
                  className="p-1 hover:bg-surface-bright/20 rounded text-on-surface-variant hover:text-on-surface"
                >
                  <PenLine className="w-3 h-3" />
                </button>
                <button
                  onClick={(e) => handleDeleteChat(e, session.id)}
                  className="p-1 hover:bg-rose-500/20 rounded text-on-surface-variant hover:text-rose-400"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            </div>
          ))}

          {sessions.length === 0 && (
            <div className="text-center py-8 text-on-surface-variant text-xs font-sans">
              No sessions yet.
            </div>
          )}
        </div>
      </div>

      {/* Main Conversation Viewport */}
      <div className="flex-1 flex flex-col h-full bg-transparent min-w-0">
        {activeSession ? (
          <>
            {/* Chat Topbar */}
            <div className="px-4 py-3 border-b border-glass-border glass-panel-deep flex flex-wrap items-center justify-between gap-3 min-w-0">
              <div className="flex items-center gap-3 min-w-0">
                <button
                  onClick={() => setShowSessionDrawer(true)}
                  className="md:hidden p-1.5 text-on-surface-variant hover:bg-surface-bright/20"
                >
                  <Menu className="w-4 h-4" />
                </button>
                <div className="min-w-0">
                  <h2 className="font-editorial text-xl sm:text-2xl text-on-surface truncate">
                    {activeSession.title}
                  </h2>
                  <p className="text-[11px] text-on-surface-variant font-sans">
                    {modesConfig.find((m) => m.id === selectedMode)?.desc}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 min-w-0 shrink-0 flex-wrap justify-end">
                {/* Mode Selector Tabs */}
                <div className="flex items-center gap-1 bg-surface-container/40 p-1 border border-glass-border">
                  {modesConfig.map((m) => {
                    const Icon = m.icon;
                    const isSelected = selectedMode === m.id;
                    return (
                      <button
                        key={m.id}
                        onClick={() => setSelectedMode(m.id as LearningMode)}
                        className={`flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold transition ${
                          isSelected
                            ? "bg-primary text-on-primary shadow-[0_0_8px_rgba(var(--accent-rgb),0.3)]"
                            : "text-on-surface-variant hover:text-on-surface"
                        }`}
                      >
                        <Icon className="w-3 h-3" />
                        <span className="hidden sm:inline">{m.label}</span>
                      </button>
                    );
                  })}
                </div>

                {/* 5-Pillar Context Panel Toggle */}
                <button
                  onClick={() => setShowContextPanel(!showContextPanel)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 border text-xs font-semibold transition ${
                    showContextPanel
                      ? "bg-primary-container/40 border-primary text-primary shadow-[0_0_10px_rgba(var(--accent-rgb),0.2)]"
                      : "bg-surface-container/40 border-glass-border text-on-surface-variant hover:text-on-surface"
                  }`}
                  title="Inspect Unified Learning Context"
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">5-Pillar Context</span>
                </button>
              </div>
            </div>

            {/* Conversation Flow Area */}
            <div className="flex-1 flex overflow-hidden">
              <div className="flex-1 flex flex-col min-w-0">
                <div ref={messagesPaneRef} className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
                  {activeSession.messages?.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex gap-3 sm:gap-4 max-w-3xl ${
                        msg.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
                      }`}
                    >
                      {msg.role === "user" ? (
                        <div className="w-7 h-7 sm:w-8 sm:h-8 flex items-center justify-center shrink-0 border border-glass-border shadow-sm bg-primary-container/40 text-luminous-highlight">
                          <User className="w-4 h-4" />
                        </div>
                      ) : (
                        // The mark itself, not a generic sparkle. Static: an
                        // answer that has already arrived is not still working.
                        <img
                          src={atlasMark}
                          alt=""
                          aria-hidden="true"
                          className="w-7 h-7 sm:w-8 sm:h-8 shrink-0 object-contain"
                        />
                      )}

                      <div
                        className={`min-w-0 px-4 sm:px-5 py-3 text-xs sm:text-sm leading-relaxed ${
                          msg.role === "user"
                            ? "bg-primary-container/40/80 text-on-surface rounded-tr-none border border-glass-border shadow-sm"
                            : "glass-card text-on-surface rounded-tl-none border border-glass-border shadow-[0_4px_20px_rgba(0,0,0,0.08)]"
                        }`}
                      >
                        <MarkdownContent
                          content={msg.content}
                          markdown={msg.role === "assistant"}
                        />
                        {msg.role === "assistant" && msg.citations && (
                          <CitationList citations={msg.citations} />
                        )}
                      </div>
                    </div>
                  ))}

                  {/* Streaming Assistant Response */}
                  {isStreaming && (
                    <div className="flex gap-3 sm:gap-4 max-w-3xl mr-auto">
                      <div className="w-7 h-7 sm:w-8 sm:h-8 flex items-center justify-center shrink-0">
                        <AtlasBlob className="w-6 h-6 sm:w-7 sm:h-7" />
                      </div>
                      {/* Before the first token there is nothing to show but
                          the wait, so say what is happening. Once the answer
                          starts it speaks for itself and the label goes. */}
                      {streamingContent ? (
                        <div className="min-w-0 glass-card rounded-tl-none px-4 sm:px-5 py-3 text-xs sm:text-sm leading-relaxed border border-glass-border">
                          <MarkdownContent content={streamingContent} />
                          <span className="inline-block w-1.5 h-4 bg-primary ml-1 animate-pulse" />
                          {streamingCitations.length > 0 && (
                            <CitationList citations={streamingCitations} />
                          )}
                        </div>
                      ) : (
                        <ThinkingIndicator />
                      )}
                    </div>
                  )}

                  {error && (
                    <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
                      {error}
                    </div>
                  )}

                </div>

                {/* Chat Message Input Bar */}
                <form
                  onSubmit={handleSendMessage}
                  className="p-3 sm:p-4 border-t border-glass-border glass-panel-deep flex items-end gap-2"
                >
                  <textarea
                    value={messageInput}
                    onChange={(e) => {
                      setMessageInput(e.target.value);
                      // Auto-resize
                      e.target.style.height = "auto";
                      e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage(e);
                      }
                    }}
                    placeholder={`Ask AI Tutor in ${selectedMode} mode...`}
                    disabled={isStreaming}
                    rows={1}
                    className="flex-1 bg-surface-container/50 border border-glass-border px-4 py-2.5 text-xs sm:text-sm text-on-surface placeholder:text-on-surface-variant/60 focus:outline-hidden focus:border-primary focus:shadow-[0_0_12px_rgba(var(--accent-rgb),0.2)] transition resize-none overflow-y-auto"
                    style={{ maxHeight: "160px" }}
                  />
                  <button
                    type="submit"
                    disabled={!messageInput.trim() || isStreaming || !wsReady}
                    className="atlas-btn atlas-btn-primary shrink-0"
                  >
                    {isStreaming ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <>
                        <span>Send</span>
                        <Send className="w-3.5 h-3.5" />
                      </>
                    )}
                  </button>
                </form>
              </div>

              {/* 5-Pillar Context Inspector Drawer */}
              {showContextPanel && (
                <div className="w-80 glass-panel-deep border-l border-glass-border p-4 flex flex-col space-y-4 overflow-y-auto shrink-0">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Layers className="w-4 h-4 text-primary" />
                      <h3 className="font-editorial text-lg text-on-surface">5-Pillar Context</h3>
                    </div>
                    <button
                      onClick={() => setShowContextPanel(false)}
                      className="p-1 text-on-surface-variant hover:bg-surface-bright/20"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  {loadingContext ? (
                    <div className="space-y-3">
                      <Skeleton className="h-16" />
                      <Skeleton className="h-16" />
                      <Skeleton className="h-16" />
                    </div>
                  ) : unifiedContext ? (
                    <div className="space-y-3 font-sans text-xs">
                      {/* Pillar 1: Cognitive Memory */}
                      <div className="p-3 bg-surface-container/40 border border-glass-border">
                        <div className="flex items-center gap-1.5 text-primary font-semibold mb-1">
                          <Brain className="w-3.5 h-3.5" />
                          <span>1. Learner Memory</span>
                        </div>
                        <p className="text-[11px] text-on-surface-variant">
                          {unifiedContext.memory?.strengths?.concat(unifiedContext.memory?.weaknesses || []).join(" • ") ||
                            "No active memory records"}
                        </p>
                      </div>

                      {/* Pillar 2: Roadmap Concept */}
                      <div className="p-3 bg-surface-container/40 border border-glass-border">
                        <div className="flex items-center gap-1.5 text-emerald-400 font-semibold mb-1">
                          <Compass className="w-3.5 h-3.5" />
                          <span>2. Active Roadmap Node</span>
                        </div>
                        <p className="text-[11px] text-on-surface-variant">
                          {unifiedContext.roadmap?.active_topic
                            ? `${unifiedContext.roadmap.active_topic} (${Math.round(
                                (unifiedContext.roadmap.mastery_score || 0) * 100
                              )}% mastery)`
                            : "General Track"}
                        </p>
                      </div>

                      {/* Pillar 3: Knowledge Graph */}
                      <div className="p-3 bg-surface-container/40 border border-glass-border">
                        <div className="flex items-center gap-1.5 text-luminous-highlight font-semibold mb-1">
                          <Share2 className="w-3.5 h-3.5" />
                          <span>3. Concept Graph</span>
                        </div>
                        <p className="text-[11px] text-on-surface-variant">
                          {unifiedContext.graph?.prerequisite_concepts?.join(", ") ||
                            "No prerequisite dependencies"}
                        </p>
                      </div>

                      {/* Pillar 4: Syllabus Structure */}
                      <div className="p-3 bg-surface-container/40 border border-glass-border">
                        <div className="flex items-center gap-1.5 text-primary font-semibold mb-1">
                          <BookOpen className="w-3.5 h-3.5" />
                          <span>4. Syllabus Overview</span>
                        </div>
                        <p className="text-[11px] text-on-surface-variant">
                          {unifiedContext.syllabus?.syllabus_title || "Integrated profile curriculum"}
                        </p>
                      </div>

                      {/* Pillar 5: Document Chunks / Citations */}
                      <div className="p-3 bg-surface-container/40 border border-glass-border">
                        <div className="flex items-center gap-1.5 text-cyan-300 font-semibold mb-1">
                          <FileText className="w-3.5 h-3.5" />
                          <span>5. Document Grounding ({unifiedContext.citations?.length || 0})</span>
                        </div>
                        <p className="text-[11px] text-on-surface-variant truncate">
                          {unifiedContext.citations?.[0]
                            ? `[${unifiedContext.citations[0].index}] ${unifiedContext.citations[0].filename}`
                            : "No grounded citations retrieved"}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center text-xs text-on-surface-variant">
                      No context loaded.
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 p-8">
            <EmptyState
              icon={MessageSquare}
              title="Start a Dialogue"
              description="Create a new dialogue or select an existing session to begin learning."
              actionLabel="New Dialogue"
              onAction={handleCreateChat}
            />
            {sessions.length > 0 && (
              <button
                onClick={() => setShowSessionDrawer(true)}
                className="md:hidden inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
              >
                <Menu className="w-3.5 h-3.5" />
                Browse {sessions.length} saved dialogue{sessions.length === 1 ? "" : "s"}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
