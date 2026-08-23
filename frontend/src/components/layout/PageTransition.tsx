import { useLocation } from "react-router-dom";
import type { ReactNode } from "react";

/**
 * Replays the page-enter animation whenever the route changes.
 *
 * The `key` is the whole point: changing it makes React discard the previous
 * subtree and mount a fresh one, which restarts the CSS animation. Toggling a
 * class instead would not -- an animation only replays if the element is new
 * or the animation name actually changes.
 *
 * `/chat/:sessionId` is deliberately collapsed to `/chat`, so switching
 * sessions inside the tutor does not remount and re-animate the whole page.
 */
export function PageTransition({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const key = pathname.startsWith("/chat") ? "/chat" : pathname;

  return (
    <div key={key} className="page-enter flex min-h-full flex-1 flex-col">
      {children}
    </div>
  );
}
