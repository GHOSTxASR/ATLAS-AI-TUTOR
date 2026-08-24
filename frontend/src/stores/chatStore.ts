import { create } from "zustand";
import { chatApi, LearningMode } from "../api/chat";
import { apiClient } from "../api/client";
import {
  ChatMessage,
  ChatMessageCreate,
  ChatSession,
  ChatSessionCreate,
  ChatSessionUpdate,
  Citation,
} from "../types";

interface ChatState {
  sessions: ChatSession[];
  activeSession: ChatSession | null;
  isLoading: boolean;
  isStreaming: boolean;
  streamingContent: string;
  streamingCitations: Citation[];
  error: string | null;
  searchQuery: string;

  // WebSocket
  ws: WebSocket | null;

  setSearchQuery: (query: string) => void;
  loadSessions: (profileId: string) => Promise<void>;
  loadSession: (profileId: string, sessionId: string) => Promise<void>;
  createSession: (
    profileId: string,
    data: ChatSessionCreate
  ) => Promise<void>;
  autotitleSession: (profileId: string, sessionId: string) => Promise<void>;
  updateSession: (
    profileId: string,
    sessionId: string,
    data: ChatSessionUpdate
  ) => Promise<void>;
  deleteSession: (profileId: string, sessionId: string) => Promise<void>;
  addMessage: (
    profileId: string,
    sessionId: string,
    data: ChatMessageCreate
  ) => Promise<void>;
  sendStreamingMessage: (
    profileId: string,
    sessionId: string,
    content: string,
    options?: { mode?: LearningMode; roadmapNodeId?: string; documentIds?: string[] }
  ) => void;
  clearActiveSession: () => void;
  disconnectWs: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  activeSession: null,
  isLoading: false,
  isStreaming: false,
  streamingContent: "",
  streamingCitations: [],
  error: null,
  searchQuery: "",
  ws: null,

  setSearchQuery: (query: string) => {
    set({ searchQuery: query });
  },

  loadSessions: async (profileId: string) => {
    set({ isLoading: true, error: null });
    try {
      const { searchQuery } = get();
      const sessions = await chatApi.getSessions(profileId, searchQuery || undefined);
      set({ sessions, isLoading: false });
    } catch (err: any) {
      set({
        error: err.message || "Failed to load chat sessions",
        isLoading: false,
      });
    }
  },

  loadSession: async (profileId: string, sessionId: string) => {
    set({ isLoading: true, error: null });
    try {
      const session = await chatApi.getSession(profileId, sessionId);
      set({ activeSession: session, isLoading: false });

      // Connect WebSocket for this session
      get().disconnectWs();
      const apiBaseUrl = new URL(apiClient.defaults.baseURL || "/", window.location.origin);
      const wsProtocol = apiBaseUrl.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${wsProtocol}//${apiBaseUrl.host}/ws/chat/${profileId}/${sessionId}`;
      const ws = new WebSocket(wsUrl);

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const state = get();

        if (data.type === "user_saved") {
          // User message was persisted by the server
          const userMsg: ChatMessage = {
            id: data.message_id,
            session_id: sessionId,
            role: "user",
            content: data.content,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          };
          if (state.activeSession && state.activeSession.id === sessionId) {
            const currentMsgs = state.activeSession.messages || [];
            // Prevent duplicate if already added
            if (!currentMsgs.some((m) => m.id === userMsg.id)) {
              set({
                activeSession: {
                  ...state.activeSession,
                  messages: [...currentMsgs, userMsg],
                },
              });
            }
          }
        } else if (data.type === "citations") {
          // Store RAG citations sent before the response stream
          set({ streamingCitations: data.citations || [] });
        } else if (data.type === "chunk") {
          set({
            isStreaming: true,
            streamingContent: state.streamingContent + data.content,
          });
        } else if (data.type === "done") {
          const finalContent = state.streamingContent;
          if (finalContent && state.activeSession && state.activeSession.id === sessionId) {
            const assistantMsg: ChatMessage = {
              id: data.message_id || `msg-${Date.now()}`,
              session_id: sessionId,
              role: "assistant",
              content: finalContent,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
              // Carry the sources through to the finished message; they were
              // previously collected and then discarded on completion.
              citations: state.streamingCitations.length
                ? state.streamingCitations
                : undefined,
            };
            const currentMsgs = state.activeSession.messages || [];
            set({
              activeSession: {
                ...state.activeSession,
                messages: [...currentMsgs, assistantMsg],
              },
              isStreaming: false,
              streamingContent: "",
              streamingCitations: [],
            });
          } else {
            set({ isStreaming: false, streamingContent: "", streamingCitations: [] });
          }
          // Bubble session to top
          const sessionToMove = state.sessions.find(
            (s) => s.id === sessionId
          );
          if (sessionToMove) {
            const rest = state.sessions.filter((s) => s.id !== sessionId);
            set({ sessions: [sessionToMove, ...rest] });
          }
        } else if (data.type === "error") {
          set({
            error: data.content,
            isStreaming: false,
            streamingContent: "",
            streamingCitations: [],
          });
        }
      };

      ws.onerror = () => {
        set({ error: "WebSocket connection error" });
      };

      ws.onclose = () => {
        const state = get();
        if (state.ws === ws) {
          set({ ws: null });
        }
      };

      set({ ws });
    } catch (err: any) {
      set({
        error: err.message || "Failed to load chat session",
        isLoading: false,
      });
    }
  },

  createSession: async (profileId: string, data: ChatSessionCreate) => {
    set({ isLoading: true, error: null });
    try {
      const newSession = await chatApi.createSession(profileId, data);
      const { sessions } = get();
      set({
        sessions: [newSession, ...sessions],
        isLoading: false,
      });
      // Load the newly created session
      await get().loadSession(profileId, newSession.id);
    } catch (err: any) {
      set({
        error: err.message || "Failed to create chat session",
        isLoading: false,
      });
    }
  },

  autotitleSession: async (profileId: string, sessionId: string) => {
    try {
      const updated = await chatApi.autotitleSession(profileId, sessionId);
      const { sessions, activeSession } = get();
      set({
        sessions: sessions.map((s) =>
          s.id === sessionId ? { ...s, title: updated.title } : s
        ),
        activeSession:
          activeSession?.id === sessionId
            ? { ...activeSession, title: updated.title }
            : activeSession,
      });
    } catch {
      // A title is cosmetic; a failure here must not disturb the conversation.
    }
  },

  updateSession: async (
    profileId: string,
    sessionId: string,
    data: ChatSessionUpdate
  ) => {
    try {
      const updatedSession = await chatApi.updateSession(
        profileId,
        sessionId,
        data
      );
      const { sessions, activeSession } = get();
      set({
        sessions: sessions.map((s) =>
          s.id === sessionId ? { ...s, ...updatedSession } : s
        ),
        activeSession:
          activeSession?.id === sessionId
            ? { ...activeSession, ...updatedSession }
            : activeSession,
      });
    } catch (err: any) {
      set({ error: err.message || "Failed to update chat session" });
    }
  },

  deleteSession: async (profileId: string, sessionId: string) => {
    set({ isLoading: true, error: null });
    try {
      await chatApi.deleteSession(profileId, sessionId);
      const { sessions, activeSession } = get();
      if (activeSession?.id === sessionId) {
        get().disconnectWs();
      }
      set({
        sessions: sessions.filter((s) => s.id !== sessionId),
        activeSession:
          activeSession?.id === sessionId ? null : activeSession,
        isLoading: false,
      });
    } catch (err: any) {
      set({
        error: err.message || "Failed to delete chat session",
        isLoading: false,
      });
    }
  },

  addMessage: async (
    profileId: string,
    sessionId: string,
    data: ChatMessageCreate
  ) => {
    try {
      const newMessage = await chatApi.addMessage(
        profileId,
        sessionId,
        data
      );
      const { activeSession, sessions } = get();

      if (activeSession && activeSession.id === sessionId) {
        const updatedMessages = activeSession.messages
          ? [...activeSession.messages, newMessage]
          : [newMessage];
        set({
          activeSession: { ...activeSession, messages: updatedMessages },
        });
      }

      const sessionToMove = sessions.find((s) => s.id === sessionId);
      if (sessionToMove) {
        const rest = sessions.filter((s) => s.id !== sessionId);
        set({ sessions: [sessionToMove, ...rest] });
      }
    } catch (err: any) {
      set({ error: err.message || "Failed to send message" });
    }
  },

  sendStreamingMessage: (
    profileId: string,
    sessionId: string,
    content: string,
    options?: { mode?: LearningMode; roadmapNodeId?: string; documentIds?: string[] }
  ) => {
    const { ws } = get();
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      set({ error: "Not connected to chat. Try reopening the session." });
      return;
    }
    set({ isStreaming: true, streamingContent: "", streamingCitations: [], error: null });
    ws.send(JSON.stringify({
      content,
      mode: options?.mode,
      roadmap_node_id: options?.roadmapNodeId,
      document_ids: options?.documentIds,
    }));
  },

  clearActiveSession: () => {
    get().disconnectWs();
    set({ activeSession: null, streamingContent: "", streamingCitations: [], isStreaming: false });
  },

  disconnectWs: () => {
    const { ws } = get();
    if (ws) {
      ws.close();
      set({ ws: null });
    }
  },
}));
