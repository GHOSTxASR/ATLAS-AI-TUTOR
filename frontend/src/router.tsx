import React, { Suspense, lazy, useEffect, useState } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { App } from "./App";
import { Spinner } from "./components/common/LoadingStates";
import { useProfileStore } from "./stores/profileStore";

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

function StartRoute() {
  const { profiles, isLoading, error, loadProfiles } = useProfileStore();
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    loadProfiles().finally(() => setLoaded(true));
  }, [loadProfiles]);

  if (!loaded || isLoading) {
    return (
      <div className="flex h-64 w-full items-center justify-center">
        <Spinner size="lg" label="Loading profiles..." />
      </div>
    );
  }

  if (error) {
    return <div className="p-8 text-center" role="alert">{error}</div>;
  }

  return <Navigate to={profiles.length > 0 ? "/dashboard" : "/setup"} replace />;
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <StartRoute /> },
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
