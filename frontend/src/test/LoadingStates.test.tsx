import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  Skeleton,
  CardSkeleton,
  TableSkeleton,
  Spinner,
  EmptyState,
  ErrorState,
} from "../components/common/LoadingStates";
import { BookOpen } from "lucide-react";

describe("LoadingStates Component Suite", () => {
  it("renders Skeleton with proper role and aria-busy attributes", () => {
    render(<Skeleton className="h-6 w-32" />);
    const skeleton = screen.getByRole("status");
    expect(skeleton).toBeInTheDocument();
    expect(skeleton).toHaveAttribute("aria-busy", "true");
  });

  it("renders CardSkeleton with multiple cards", () => {
    const { container } = render(<CardSkeleton count={3} />);
    const cards = container.querySelectorAll(".p-5");
    expect(cards.length).toBe(3);
  });

  it("renders Spinner with accessible text", () => {
    render(<Spinner size="md" label="Loading data..." />);
    expect(screen.getByText("Loading data...")).toBeInTheDocument();
  });

  it("renders EmptyState with title, description, and optional action button", () => {
    render(
      <EmptyState
        icon={BookOpen}
        title="No Lessons Found"
        description="Create your first study note above."
        actionLabel="Create Note"
        onAction={() => {}}
      />
    );
    expect(screen.getByText("No Lessons Found")).toBeInTheDocument();
    expect(screen.getByText("Create your first study note above.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Note" })).toBeInTheDocument();
  });

  it("renders ErrorState with alert role and retry button", () => {
    let retried = false;
    render(
      <ErrorState
        title="Failed to Load Notes"
        message="Network connection timed out."
        onRetry={() => {
          retried = true;
        }}
      />
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Failed to Load Notes")).toBeInTheDocument();
    expect(screen.getByText("Network connection timed out.")).toBeInTheDocument();

    const retryBtn = screen.getByRole("button", { name: /retry/i });
    retryBtn.click();
    expect(retried).toBe(true);
  });
});
