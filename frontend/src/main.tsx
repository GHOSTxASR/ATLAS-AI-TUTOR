import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";

import { router } from "./router";
import { CustomCursor } from "./components/common/CustomCursor";
// KaTeX ships its own stylesheet; without it rendered formulas are unreadable.
import "katex/dist/katex.min.css";
import "./styles/fonts.css";
import "./styles/tokens.css";
import "./styles/globals.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 300_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <CustomCursor />
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>
);
