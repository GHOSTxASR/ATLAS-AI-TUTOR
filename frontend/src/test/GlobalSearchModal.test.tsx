import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { GlobalSearchModal } from "../components/common/GlobalSearchModal";
import { useProfileStore } from "../stores/profileStore";
import { searchApi } from "../api/search";

// Mock search API
vi.mock("../api/search", () => ({
  searchApi: {
    globalSearch: vi.fn(),
  },
}));

describe("GlobalSearchModal Component & Integration Tests", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useProfileStore.setState({ activeProfileId: "prof-123" });
  });

  it("does not render when isOpen is false", () => {
    render(
      <MemoryRouter>
        <GlobalSearchModal isOpen={false} onClose={vi.fn()} />
      </MemoryRouter>
    );
    expect(screen.queryByPlaceholderText(/search chats/i)).not.toBeInTheDocument();
  });

  it("renders search input, category filters, and close on Escape key", async () => {
    const onCloseMock = vi.fn();
    render(
      <MemoryRouter>
        <GlobalSearchModal isOpen={true} onClose={onCloseMock} />
      </MemoryRouter>
    );

    expect(screen.getByPlaceholderText(/search chats/i)).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "All" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /chats/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /notes/i })).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onCloseMock).toHaveBeenCalled();
  });

  it("fetches and displays search results when query is entered", async () => {
    (searchApi.globalSearch as any).mockResolvedValue({
      query: "Thermodynamics",
      total_results: 1,
      chats: [],
      notes: [
        {
          id: "note-1",
          title: "First Law of Thermodynamics",
          subtitle: "Lesson Note",
          snippet: "Conservation of energy in thermodynamic systems.",
          category: "notes",
          url_path: "/notes?note_id=note-1",
          score: 1.0,
        },
      ],
      documents: [],
      graph: [],
      roadmap: [],
    });

    render(
      <MemoryRouter>
        <GlobalSearchModal isOpen={true} onClose={vi.fn()} />
      </MemoryRouter>
    );

    const input = screen.getByPlaceholderText(/search chats/i);
    fireEvent.change(input, { target: { value: "Thermodynamics" } });

    await waitFor(() => {
      expect(screen.getByText("First Law of Thermodynamics")).toBeInTheDocument();
      expect(screen.getByText("Conservation of energy in thermodynamic systems.")).toBeInTheDocument();
    });
  });
});
