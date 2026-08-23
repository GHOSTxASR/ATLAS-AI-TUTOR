import React, { Suspense, lazy } from "react";
import { createBrowserRouter } from "react-router-dom";
import { App } from "./App";
import { Spinner } from "./components/common/LoadingStates";

const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage").then(m => ({ default: m.AnalyticsPage })));
const ChatPage = lazy(() => import("./pages/ChatPage").then(m => ({ default: m.ChatPage })));
const DashboardPage = lazy(() => import("./pages/DashboardPage").then(m => ({ default: m.DashboardPage })));
const DocumentsPage = lazy(() => import("./pages/DocumentsPage").then(m => ({ default: m.DocumentsPage })));
const GraphPage = lazy(() => import("./pages/GraphPage").then(m => ({ default: m.GraphPage })));
const MemoryPage = lazy(() => import("./pages/MemoryPage").then(m => ({ default: m.MemoryPage })));
const NotesPage = lazy(() => import("./pages/NotesPage").then(m => ({ default: m.NotesPage })));
const QuizPage = lazy(() => import("./pages/QuizPage").then(m => ({ default: m.QuizPage })));
const RoadmapPage = lazy(() => import("./pages/RoadmapPage").then(m => ({ default: m.RoadmapPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then(m => ({ default: m.SettingsPage })));
const SetupPage = lazy(() => import("./pages/SetupPage").then(m => ({ default: m.SetupPage })));
const LandingPage = lazy(() => import("./pages/LandingPage").then(m => ({ default: m.LandingPage })));

function PageSuspense({ children }: { children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="flex h-64 w-full items-center justify-center">
          <Spinner size="lg" label="Loading page..." />
        </div>
      }
    >
      {children}
    </Suspense>
  );
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: (
      <PageSuspense>
        <LandingPage />
      </PageSuspense>
    ),
  },
  {
    path: "/",
    element: <App />,
    children: [
      { path: "setup", element: <PageSuspense><SetupPage /></PageSuspense> },
      { path: "dashboard", element: <PageSuspense><DashboardPage /></PageSuspense> },
      { path: "chat", element: <PageSuspense><ChatPage /></PageSuspense> },
      { path: "chat/:sessionId", element: <PageSuspense><ChatPage /></PageSuspense> },
      { path: "roadmap", element: <PageSuspense><RoadmapPage /></PageSuspense> },
      { path: "notes", element: <PageSuspense><NotesPage /></PageSuspense> },
      { path: "documents", element: <PageSuspense><DocumentsPage /></PageSuspense> },
      { path: "graph", element: <PageSuspense><GraphPage /></PageSuspense> },
      { path: "quiz", element: <PageSuspense><QuizPage /></PageSuspense> },
      { path: "analytics", element: <PageSuspense><AnalyticsPage /></PageSuspense> },
      { path: "memory", element: <PageSuspense><MemoryPage /></PageSuspense> },
      { path: "settings", element: <PageSuspense><SettingsPage /></PageSuspense> },
    ],
  },
], {
  future: { v7_startTransition: true },
});
