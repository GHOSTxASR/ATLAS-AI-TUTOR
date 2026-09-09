import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

import { chatApi } from "../api/chat";
import { getErrorMessage } from "../utils/errors";

/**
 * Marker put on the navigation when the tutor is opened to study something.
 *
 * Carried in router state rather than the URL on purpose. A query parameter
 * survives a reload, so refreshing the page would ask the tutor to start over;
 * router state does not, which is the behaviour wanted here.
 */
export interface StudyIntent {
  studyTopic: string;
}

/** The first thing said on the learner's behalf when a topic is opened. */
export function openingPromptFor(topic: string): string {
  return `Teach me "${topic}". Assume I am starting from scratch.`;
}

/**
 * Open the tutor on a topic, from the roadmap or the knowledge graph.
 *
 * Every entry point used to stop short of actually starting: the roadmap
 * button created the session and navigated, and the "Study" links only dropped
 * the topic name into the message box. Either way the tutor was handed nothing
 * and sat silent, so clicking "Start AI Tutorial" appeared to do nothing at
 * all.
 *
 * Resolving the session through `for-topic` also keeps the thread attached to
 * its roadmap node, which is what lets the backend pull in prerequisites and
 * move the topic off "not started".
 */
export function useOpenTutor() {
  const navigate = useNavigate();
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const openTutor = useCallback(
    async (profileId: string, topic: string, roadmapNodeId?: string) => {
      if (!profileId || !topic.trim() || opening) return;
      setOpening(true);
      setError(null);
      try {
        const session = await chatApi.sessionForTopic(profileId, topic, roadmapNodeId);
        const intent: StudyIntent = { studyTopic: topic };
        navigate(`/chat/${session.id}`, { state: intent });
      } catch (err) {
        setError(getErrorMessage(err, "Could not open the tutor for this topic."));
      } finally {
        setOpening(false);
      }
    },
    [navigate, opening],
  );

  return { openTutor, opening, error, clearError: () => setError(null) };
}
